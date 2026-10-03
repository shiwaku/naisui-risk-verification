"""基準手法 B3: 地形分類の内水関連区分。docs/method-survey.md §6.2

    uv run python scripts/fetch_landform.py
    uv run python scripts/prepare_trial.py
    uv run python scripts/baseline_b3.py

ビューワの「内水関連のみ」と同じ区分（viewer/src/landform-codes.json の naisui）を内水が起きやすい所とみなす。
- 自然地形: 凹地・浅い谷、後背低地・湿地、旧河道、落堀、旧水部
- 人工地形: 干拓地、盛土地・埋立地
人工地形は自然地形の上に重なる（同じ場所に両方ある）ので、別々に格子にする。

出力（data/interim/tottori/）:
- landform_natural.tif / landform_artificial.tif  区分の番号（landform-codes.json の classes の順に 1 から。0: なし）
- b3_naisui_natural.tif / b3_naisui_artificial.tif / b3_naisui_any.tif  内水関連の区分なら 1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "interim" / "tottori"
LANDFORM = ROOT / "data" / "raw" / "landform" / "tottori_landform.geojson"
CODES = ROOT / "viewer" / "src" / "landform-codes.json"


def load_classes() -> tuple[list[dict], dict[str, int]]:
    classes = json.loads(CODES.read_text(encoding="utf-8"))["classes"]
    by_code = {c: i + 1 for i, cls in enumerate(classes) for c in cls["codes"]}
    return classes, by_code


def main() -> int:
    if not LANDFORM.exists() or not (WORK / "dem_1m.tif").exists():
        print("先に scripts/fetch_landform.py と scripts/prepare_trial.py を実行する", file=sys.stderr)
        return 1
    with rasterio.open(WORK / "dem_1m.tif") as src:
        profile = src.profile | dict(dtype="uint8", nodata=None)
        shape, transform, crs = (src.height, src.width), src.transform, src.crs

    classes, by_code = load_classes()
    naisui_ids = np.array([0] + [1 if c["naisui"] else 0 for c in classes], dtype="uint8")
    lf = gpd.read_file(LANDFORM).to_crs(crs)
    lf["cls"] = lf["code"].astype(str).map(by_code)
    unknown = sorted(lf.loc[lf["cls"].isna(), "code"].unique())
    if unknown:
        print(f"  表にないコード（区分なしとして扱う）: {unknown}")
    lf = lf.dropna(subset=["cls"])

    naisui = {}
    for kind in ["natural", "artificial"]:
        g = lf[lf["kind"] == kind]
        idx = rasterize(((geom, int(c)) for geom, c in zip(g.geometry, g["cls"])), shape, transform=transform,
                        dtype="uint8")
        with rasterio.open(WORK / f"landform_{kind}.tif", "w", **profile) as dst:
            dst.write(idx, 1)
        naisui[kind] = naisui_ids[idx]
    naisui["any"] = naisui["natural"] | naisui["artificial"]
    for name, mask in naisui.items():
        with rasterio.open(WORK / f"b3_naisui_{name}.tif", "w", **profile) as dst:
            dst.write(mask, 1)
        print(f"  b3_naisui_{name}.tif: {mask.mean():.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
