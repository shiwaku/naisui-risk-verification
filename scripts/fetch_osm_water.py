"""試行範囲（鳥取市）の水面・水路を OpenStreetMap から取得する。

    uv run python scripts/fetch_osm_water.py

Overpass API で、計算範囲（prepare_trial.py）の外接矩形にある次の地物を取る。
- 水路の線: waterway=river / stream / canal / drain / ditch
- 水面の面: natural=water、waterway=riverbank

出力: data/raw/osm/tottori_water.geojson（EPSG:4326、取得済みなら飛ばす）
データ: © OpenStreetMap contributors（ODbL）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "osm" / "tottori_water.geojson"

OVERPASS = "https://overpass-api.de/api/interpreter"
# 南, 西, 北, 東（計算範囲 EPSG:6673 -17490,-61370 – -3410,-49210 を緯度経度にしたもの）
BBOX = (35.4466, 134.1404, 35.5565, 134.2958)
WATERWAYS = "river|stream|canal|drain|ditch"


def query() -> dict:
    s, w, n, e = BBOX
    q = f"""
[out:json][timeout:180];
(
  way["waterway"~"^({WATERWAYS})$"]({s},{w},{n},{e});
  way["natural"="water"]({s},{w},{n},{e});
  way["waterway"="riverbank"]({s},{w},{n},{e});
  relation["natural"="water"]({s},{w},{n},{e});
);
out tags geom;
"""
    r = requests.post(OVERPASS, data={"data": q}, timeout=300,
                      headers={"User-Agent": "naisui-risk-verification (research)"})
    r.raise_for_status()
    return r.json()


def to_features(data: dict) -> gpd.GeoDataFrame:
    rows = []
    for el in data["elements"]:
        tags = el.get("tags", {})
        kind = tags.get("waterway") or tags.get("natural")
        if el["type"] == "way":
            coords = [(p["lon"], p["lat"]) for p in el["geometry"]]
            closed = len(coords) >= 4 and coords[0] == coords[-1]
            if tags.get("waterway") in WATERWAYS.split("|"):
                geom = LineString(coords)
            elif closed:
                geom = Polygon(coords)
            else:
                continue
        else:  # relation（multipolygon の外周だけ使う）
            outers = [[(p["lon"], p["lat"]) for p in m["geometry"]]
                      for m in el.get("members", []) if m.get("role") == "outer" and "geometry" in m]
            polys = [Polygon(c) for c in outers if len(c) >= 4 and c[0] == c[-1]]
            if not polys:
                continue
            geom = polys[0] if len(polys) == 1 else gpd.GeoSeries(polys).union_all()
        rows.append({"osm_id": f"{el['type']}/{el['id']}", "kind": kind, "name": tags.get("name"),
                     "width": tags.get("width"), "geometry": geom})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def main() -> int:
    if OUT.exists():
        print(f"取得済み: {OUT.relative_to(ROOT)}")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    gdf = to_features(query())
    if gdf.empty:
        print("水面・水路が取れなかった", file=sys.stderr)
        return 1
    gdf.to_file(OUT, driver="GeoJSON")
    print(f"  {OUT.relative_to(ROOT)}（{len(gdf):,} 件）")
    print(json.dumps(gdf["kind"].value_counts().to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
