"""浸水実績と内水浸水想定区域（A51）の両方がある市町村を洗い出す。

    uv run python scripts/download.py            # 先に元データを取得
    uv run python scripts/select_municipalities.py

出力:
- output/municipalities.csv   A51 がある全市町村の集計（両方あるかの判定つき）
- 標準出力                     両方ある市町村の一覧

判定:
- 内水浸水想定区域: A51 の市町村コード（A51_004）でその市町村の区域がある
- 浸水実績: 浸水実績ポリゴンと市町村の境界（N03）が重なる面積が MIN_SINSUI_M2 以上

浸水実績は内水と外水が混ざっている。ここでは「重なる浸水実績があるか」だけを見て、
内水と外水の切り分けは評価の段階で行う（docs/method-survey.md §7）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "output"

# これ未満の重なりは、境界の位置ずれや隣接市町村の浸水域の端とみなして数えない
MIN_SINSUI_M2 = 10_000  # 1 ha

# 面積計算に使う等積図法（アルベルス正積円錐図法、日本全域を1つで扱う）。
# 市町村どうしの比較が目的なので、平面直角座標系の系を市町村ごとに切り替えるほどの精度は要らない。
AREA_CRS = "+proj=aea +lat_1=30 +lat_2=40 +lat_0=35 +lon_0=137 +ellps=GRS80 +units=m +no_defs"

# A51 の浸水深区分のうち 0.5m 以上（床上浸水の目安）
DEEP_CLASSES = {
    "0.5m以上1m未満", "1m以上3m未満", "3m以上5m未満",
    "5m以上10m未満", "10m以上20m未満", "20m以上",
}


def read_a51() -> gpd.GeoDataFrame:
    paths = sorted((RAW / "A51").glob("*/**/*.shp"))
    frames = [pyogrio.read_dataframe(p) for p in paths]
    a51 = pd.concat(frames, ignore_index=True)
    a51 = gpd.GeoDataFrame(a51, geometry="geometry", crs=frames[0].crs)
    a51 = a51.rename(columns={"A51_001": "pref", "A51_003": "a51_name", "A51_004": "code", "A51_005": "depth"})
    a51["code"] = a51["code"].astype(str).str.zfill(5)
    return a51


def read_n03() -> gpd.GeoDataFrame:
    paths = sorted((RAW / "N03").glob("*/*.shp"))
    n03 = pd.concat([pyogrio.read_dataframe(p) for p in paths], ignore_index=True)
    n03 = gpd.GeoDataFrame(n03, geometry="geometry", crs="EPSG:6668")
    n03 = n03[n03["N03_007"].notna()].copy()
    n03["code"] = n03["N03_007"].astype(str).str.zfill(5)
    # 政令市の区は N03_005 に区名が入る。市町村名は郡・政令市名と区名をつなげて表す
    n03["name"] = n03[["N03_003", "N03_004", "N03_005"]].fillna("").agg("".join, axis=1)
    n03 = n03.dissolve(by="code", aggfunc={"N03_001": "first", "N03_004": "first", "N03_005": "first", "name": "first"}).reset_index()

    # 政令市: N03 は区ごとのコード（市名は N03_004、区名は N03_005）（例: 広島市中区 34101）だが、A51 は市のコード（34100）で持つ。
    # 区をまとめた市の行を足す。市のコードは「最小の区コード − 1」（札幌 01100、横浜 14100、福岡 40130…）
    wards = n03[n03["N03_005"].fillna("") != ""]
    cities = wards.dissolve(by=["N03_001", "N03_004"], aggfunc={"code": "min"}).reset_index()
    cities["code"] = (cities["code"].astype(int) - 1).astype(str).str.zfill(5)
    cities["name"] = cities["N03_004"]
    cities["N03_005"] = ""
    n03 = pd.concat([n03, cities[n03.columns]], ignore_index=True)
    return gpd.GeoDataFrame(n03, geometry="geometry", crs="EPSG:6668").rename(columns={"N03_001": "pref"})


def main() -> int:
    OUT.mkdir(exist_ok=True)

    print("A51 を読み込み中…")
    a51 = read_a51().to_crs(AREA_CRS)
    a51["area"] = a51.geometry.area
    a51_stats = a51.groupby("code").agg(
        a51_name=("a51_name", "first"),
        a51_km2=("area", lambda s: s.sum() / 1e6),
        a51_deep_km2=("area", lambda s: s[a51.loc[s.index, "depth"].isin(DEEP_CLASSES)].sum() / 1e6),
        a51_features=("area", "size"),
    )
    print(f"  A51: {len(a51_stats)} 市町村")

    print("N03 を読み込み中…")
    n03 = read_n03().to_crs(AREA_CRS)
    n03 = n03[n03["code"].isin(a51_stats.index)].copy()
    n03["muni_km2"] = n03.geometry.area / 1e6

    print("浸水実績と重ね合わせ中…")
    sinsui = gpd.read_file(RAW / "sinsui" / "sinsui_all.gpkg", layer="sinsui").to_crs(AREA_CRS)
    sinsui["typhoon"] = sinsui["disastName"].fillna("").str.contains("台風") | (
        sinsui["disastName"].fillna("").eq("") & sinsui["typhoon_file"].astype(bool)
    )
    inter = gpd.overlay(
        sinsui[["src_file", "event_year", "typhoon", "geometry"]],
        n03[["code", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    inter["area"] = inter.geometry.area
    per_event = inter.groupby(["code", "src_file"]).agg(
        area=("area", "sum"), year=("event_year", "first"), typhoon=("typhoon", "any")
    ).reset_index()
    per_event = per_event[per_event["area"] >= MIN_SINSUI_M2]
    sinsui_stats = per_event.groupby("code").agg(
        sinsui_events=("src_file", "nunique"),
        sinsui_events_non_typhoon=("typhoon", lambda s: int((~s).sum())),
        sinsui_first_year=("year", "min"),
        sinsui_last_year=("year", "max"),
    )
    # 浸水実績の面積は、重なった複数イベントの和集合で数える（同じ場所を二重に数えない）
    kept = inter.merge(per_event[["code", "src_file"]], on=["code", "src_file"])
    sinsui_union = kept.dissolve(by="code")[["geometry"]]
    union_area = sinsui_union.geometry.area.div(1e6).rename("sinsui_km2")

    print("A51 と浸水実績の重なりを計算中…")
    a51_union = a51.dissolve(by="code")[["geometry"]]
    both = a51_union.join(sinsui_union, lsuffix="_a51", rsuffix="_sinsui", how="inner")
    overlap = gpd.GeoSeries(both["geometry_a51"], crs=AREA_CRS).intersection(
        gpd.GeoSeries(both["geometry_sinsui"], crs=AREA_CRS)
    )
    overlap_km2 = overlap.area.div(1e6).rename("a51_sinsui_overlap_km2")

    table = (
        n03.set_index("code")[["pref", "name", "muni_km2"]]
        .join(a51_stats, how="right")
        .join(sinsui_stats)
        .join(union_area)
        .join(overlap_km2)
    )
    table["sinsui_events"] = table["sinsui_events"].fillna(0).astype(int)
    table["sinsui_events_non_typhoon"] = table["sinsui_events_non_typhoon"].fillna(0).astype(int)
    table[["sinsui_km2", "a51_sinsui_overlap_km2"]] = table[["sinsui_km2", "a51_sinsui_overlap_km2"]].fillna(0.0)
    table["has_both"] = table["sinsui_events"] > 0
    # 内水浸水想定区域のうち、浸水実績と重なる割合（実績を想定区域がどれだけ説明するかの目安）
    table["a51_covered_by_sinsui"] = (table["a51_sinsui_overlap_km2"] / table["a51_km2"]).round(3)
    table = table.sort_values(["has_both", "a51_sinsui_overlap_km2"], ascending=[False, False])

    num = ["muni_km2", "a51_km2", "a51_deep_km2", "sinsui_km2", "a51_sinsui_overlap_km2"]
    table[num] = table[num].round(2)
    table.to_csv(OUT / "municipalities.csv", encoding="utf-8-sig")

    both = table[table["has_both"]]
    print(f"\nA51 がある市町村 {len(table)} / うち浸水実績とも重なる市町村 {len(both)}\n")
    cols = ["pref", "name", "a51_km2", "a51_deep_km2", "sinsui_events", "sinsui_events_non_typhoon",
            "sinsui_first_year", "sinsui_last_year", "sinsui_km2", "a51_sinsui_overlap_km2"]
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(both[cols].to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
