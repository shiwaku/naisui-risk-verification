"""試行範囲（鳥取市）の地形分類（国土地理院 ベクトルタイル提供実験）を取得する。

    uv run python scripts/fetch_landform.py

計算範囲（prepare_trial.py）の外接矩形にかかる z14 の GeoJSON タイルを、自然地形と人工地形の両方取る。
z14 は詳細版で、凹地・旧河道・後背低地などの内水に効く分類がある（viewer/src/landform.ts の説明と同じ）。
タイルの境界で切れた地物はそのまま並べる（格子にするだけなので困らない）。

出力: data/raw/landform/tottori_landform.geojson（EPSG:4326、取得済みなら飛ばす）
  - kind: natural（自然地形）/ artificial（人工地形）
  - code: 地形分類のコード（viewer/src/landform-codes.json の codes と対応）
出典: 国土地理院 ベクトルタイル提供実験（地形分類）
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "landform" / "tottori_landform.geojson"

GSI = "https://cyberjapandata.gsi.go.jp/xyz"
KINDS = {"natural": "experimental_landformclassification1", "artificial": "experimental_landformclassification2"}
ZOOM = 14
# 南, 西, 北, 東（fetch_osm_water.py と同じ計算範囲）
BBOX = (35.4466, 134.1404, 35.5565, 134.2958)


def tile_xy(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2**z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def main() -> int:
    if OUT.exists():
        print(f"取得済み: {OUT.relative_to(ROOT)}")
        return 0
    s, w, n, e = BBOX
    x0, y0 = tile_xy(n, w, ZOOM)
    x1, y1 = tile_xy(s, e, ZOOM)
    frames = []
    session = requests.Session()
    for kind, d in KINDS.items():
        got = 0
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                r = session.get(f"{GSI}/{d}/{ZOOM}/{x}/{y}.geojson", timeout=60)
                time.sleep(0.2)  # 地理院のサーバに負荷をかけない
                if r.status_code == 404:  # データが無い区域
                    continue
                r.raise_for_status()
                feats = r.json().get("features", [])
                if not feats:
                    continue
                g = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
                g["kind"] = kind
                frames.append(g[["kind", "code", "geometry"]])
                got += 1
        print(f"  {kind}: {got} 枚")
    if not frames:
        print("地形分類が取れなかった", file=sys.stderr)
        return 1
    gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    gdf["code"] = gdf["code"].astype(str)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT, driver="GeoJSON")
    print(f"  {OUT.relative_to(ROOT)}（{len(gdf):,} 件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
