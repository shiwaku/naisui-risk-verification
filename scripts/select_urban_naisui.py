"""都市型水害（都市部の内水被害）の発生地を市区町村単位で洗い出す。

    uv run python scripts/download.py               # A16・A51 など
    uv run python scripts/fetch_suigai_toukei.py
    uv run python scripts/aggregate_suigai_naisui.py
    uv run python scripts/select_urban_naisui.py

出力: output/urban_naisui_municipalities.csv

判定（説明しやすさを優先した単純な基準）:
- 都市部: 人口集中地区（DID、令和2年国勢調査）に住む人が、市区町村の人口の URBAN_DID_POP_PCT % 以上
- 都市型水害の発生地: 都市部で、2010〜2023年の内水・窪地内水による床上＋床下の浸水が MIN_BUILDINGS 棟以上

水害統計は市区町村単位の記録で、市区町村の中の位置は分からない。そのため判定も市区町村単位で行う。
付ける列:
- has_a51: 国土数値情報 A51（雨水出水浸水想定区域）がある。政令市の区は市のコードで判定する
- hires_dem_pref: 市街地を覆う都道府県の高解像度標高がある都道府県（docs/elevation-sources.md §2）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyogrio

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "output"

URBAN_DID_POP_PCT = 50.0
MIN_BUILDINGS = 100

PREFS = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県",
    "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

# 市街地を覆う高解像度の標高（LP の DEM・DSM・点群）がある都道府県（docs/elevation-sources.md §2 で ◎）
HIRES_DEM_PREFS = {"東京都", "静岡県", "山梨県", "神奈川県", "兵庫県", "鳥取県"}


def read_did() -> pd.DataFrame:
    paths = sorted((RAW / "A16").glob("*/*_DID.shp"))
    d = pd.concat([pyogrio.read_dataframe(p, read_geometry=False) for p in paths], ignore_index=True)
    d["code"] = d["A16_002"].astype(str).str.zfill(5)
    d["pref"] = d["code"].str[:2].astype(int).map(lambda i: PREFS[i - 1])
    # 1つの市区町村に DID が複数ある場合は足す（割合も市区町村全体に対する値なので足してよい）
    g = d.groupby(["pref", "A16_003", "code"], as_index=False).agg(
        did_pop=("A16_005", "sum"),
        did_km2=("A16_006", "sum"),
        did_pop_pct=("A16_009", "sum"),
        did_area_pct=("A16_010", "sum"),
    )
    g = g.rename(columns={"A16_003": "muni"})

    # 水害統計は政令市を区ではなく市でまとめて書くことがある（例: 新潟市）。区の DID を市にまとめた行を足す。
    # 市の DID 人口割合は、区の人口（DID 人口 ÷ 割合）を足し上げて求める。
    wards = g[g["muni"].str.contains(r"市.+区$", regex=True)].copy()
    wards["city"] = wards["muni"].str.replace(r"(市).+区$", r"\1", regex=True)
    wards["pop"] = wards["did_pop"] / (wards["did_pop_pct"] / 100)
    cities = wards.groupby(["pref", "city"], as_index=False).agg(
        did_pop=("did_pop", "sum"), did_km2=("did_km2", "sum"), pop=("pop", "sum"), code=("code", "min")
    )
    cities["did_pop_pct"] = cities["did_pop"] / cities["pop"] * 100
    cities["did_area_pct"] = float("nan")
    cities["code"] = cities["code"].map(lambda c: f"{int(c) - 1:05d}")
    cities = cities.rename(columns={"city": "muni"})[g.columns]
    return pd.concat([g, cities], ignore_index=True)


def city_code_of_ward(did: pd.DataFrame) -> dict[str, str]:
    """政令市の区のコード → 市のコード（最小の区コード − 1、札幌 01100・福岡 40130 など）。"""
    wards = did[did["muni"].str.contains(r"市.+区$", regex=True)].copy()
    wards["city"] = wards["muni"].str.replace(r"(市).+区$", r"\1", regex=True)
    out: dict[str, str] = {}
    for _, grp in wards.groupby(["pref", "city"]):
        city = f"{int(grp['code'].min()) - 1:05d}"
        out.update({c: city for c in grp["code"]})
    return out


def main() -> int:
    naisui = pd.read_csv(OUT / "suigai_naisui_by_muni.csv")
    did = read_did()

    a51_codes = set(pd.read_csv(OUT / "municipalities.csv", dtype={"code": str})["code"])
    ward_to_city = city_code_of_ward(did)

    t = naisui.merge(did, on=["pref", "muni"], how="left")
    t["did_pop_pct"] = t["did_pop_pct"].fillna(0.0).round(1)
    t["did_pop"] = t["did_pop"].fillna(0).astype(int)
    t["urban"] = t["did_pop_pct"] >= URBAN_DID_POP_PCT
    t["urban_naisui"] = t["urban"] & (t["buildings"] >= MIN_BUILDINGS)
    t["has_a51"] = t["code"].isin(a51_codes) | t["code"].map(ward_to_city).isin(a51_codes)
    t["hires_dem_pref"] = t["pref"].isin(HIRES_DEM_PREFS)

    cols = [
        "pref", "muni", "code", "did_pop", "did_pop_pct", "urban", "urban_naisui",
        "records", "years", "first_year", "last_year", "area_takuchi_km2", "area_km2", "yukaue", "yukashita", "buildings",
        "buildings_台風", "buildings_梅雨前線", "buildings_豪雨・その他", "buildings_その他",
        "kubochi_records", "has_a51", "hires_dem_pref",
    ]
    t = t[cols].sort_values(["urban_naisui", "buildings"], ascending=[False, False])
    t.to_csv(OUT / "urban_naisui_municipalities.csv", index=False, encoding="utf-8-sig")

    unmatched = t[t["code"].isna()]
    sel = t[t["urban_naisui"]]
    print(f"内水被害のある市区町村 {len(t)}（DID と名前が合わない {len(unmatched)}）")
    print(f"うち都市部（DID 人口割合 {URBAN_DID_POP_PCT:.0f}% 以上） {int(t['urban'].sum())}")
    print(f"うち都市型水害の発生地（床上＋床下 {MIN_BUILDINGS} 棟以上） {len(sel)}")
    print(f"  A51 あり {int(sel['has_a51'].sum())} / 高解像度の標高がある都道府県 {int(sel['hires_dem_pref'].sum())}\n")
    show = ["pref", "muni", "did_pop_pct", "years", "yukaue", "yukashita", "buildings", "has_a51", "hires_dem_pref"]
    with pd.option_context("display.max_rows", 80, "display.width", 200):
        print(sel[show].head(60).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
