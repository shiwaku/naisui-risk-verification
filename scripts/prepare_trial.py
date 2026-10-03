"""段階1の試行（鳥取市）の入力を、同じ 1m 格子にそろえる。

    uv run python scripts/download.py        # A51・N03・A16
    uv run python scripts/prepare_trial.py

前提: 鳥取県 DEM 0.5m（G空間情報センター dem05_tottori）のうち、計算範囲にかかるタイルを
data/raw/dem05_tottori/ に置き、tottori_roi.vrt にまとめてあること。

出力（data/interim/tottori/、平面直角座標系 V系 EPSG:6673、1m）:
- dem_1m.tif     標高。0.5m を平均して 1m にした
- a51_class.tif  A51 の浸水深の区分（0: 区域外、1: 0.3m未満 … 6: 5m以上10m未満）
- did.tif        人口集中地区（令和2年）の中なら 1
- city.tif       鳥取市の中なら 1

範囲（docs/study-area-selection.md §5「市町村の境界で DEM を切らない」）:
- 計算範囲は、A51 と DID の外接矩形に BUFFER_M のバッファを付けたもの。
- 評価は DID の中だけで行う（evaluate_baselines.py）。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import reproject
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "interim" / "tottori"

CITY_CODE = "31201"
CRS = "EPSG:6673"
RES = 1.0
BUFFER_M = 2000
SNAP_M = 10

DEM_VRT = RAW / "dem05_tottori" / "tottori_roi.vrt"
A51 = RAW / "A51" / "A51-25_31_GML" / CITY_CODE / f"A51-25_{CITY_CODE}.geojson"
N03 = RAW / "N03" / "N03-20250101_31_GML" / "N03-20250101_31.geojson"
A16 = RAW / "A16" / "A16-20_31_GML" / "A16-20_31_DID.geojson"

# A51_005 の浸水深の区分。値が大きいほど深い
DEPTH_CLASSES = ["0.3m未満", "0.3m以上0.5m未満", "0.5m以上1m未満", "1m以上3m未満", "3m以上5m未満", "5m以上10m未満"]

NODATA = -9999.0


def write(path: Path, arr: np.ndarray, profile: dict, **kw) -> None:
    p = profile | kw
    with rasterio.open(path, "w", **p) as dst:
        dst.write(arr, 1)
    print(f"  {path.relative_to(ROOT)}")


def main() -> int:
    if not DEM_VRT.exists():
        print(f"DEM がない: {DEM_VRT.relative_to(ROOT)}", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    a51 = gpd.read_file(A51).to_crs(CRS)
    a51["cls"] = a51["A51_005"].map({c: i + 1 for i, c in enumerate(DEPTH_CLASSES)})
    if a51["cls"].isna().any():
        print(f"未知の浸水深の区分: {sorted(a51.loc[a51.cls.isna(), 'A51_005'].unique())}", file=sys.stderr)
        return 1
    did = gpd.read_file(A16).to_crs(CRS)
    did = did[did["A16_002"] == CITY_CODE]
    city = gpd.read_file(N03).to_crs(CRS)
    city = city[city["N03_007"] == CITY_CODE]

    minx, miny, maxx, maxy = box(*gpd.GeoSeries([a51.union_all(), did.union_all()], crs=CRS).total_bounds).buffer(
        BUFFER_M, join_style=2
    ).bounds
    minx, miny = math.floor(minx / SNAP_M) * SNAP_M, math.floor(miny / SNAP_M) * SNAP_M
    maxx, maxy = math.ceil(maxx / SNAP_M) * SNAP_M, math.ceil(maxy / SNAP_M) * SNAP_M
    width, height = int((maxx - minx) / RES), int((maxy - miny) / RES)
    transform = from_origin(minx, maxy, RES, RES)
    print(f"計算範囲 {minx:.0f},{miny:.0f} – {maxx:.0f},{maxy:.0f}（{width} x {height} セル）")

    base = dict(driver="GTiff", width=width, height=height, count=1, crs=CRS, transform=transform,
                tiled=True, blockxsize=512, blockysize=512, compress="deflate", BIGTIFF="IF_SAFER")

    dem = np.full((height, width), NODATA, dtype="float32")
    with rasterio.open(DEM_VRT) as src:
        reproject(rasterio.band(src, 1), dem, dst_transform=transform, dst_crs=CRS,
                  dst_nodata=NODATA, resampling=Resampling.average, num_threads=8)
    write(OUT / "dem_1m.tif", dem, base, dtype="float32", nodata=NODATA)  # WhiteboxTools は PREDICTOR=3 を読めない

    shapes = ((g, int(c)) for g, c in zip(a51.geometry, a51["cls"]))
    write(OUT / "a51_class.tif", rasterize(shapes, (height, width), transform=transform, dtype="uint8"),
          base, dtype="uint8", nodata=None)
    write(OUT / "did.tif", rasterize(((g, 1) for g in did.geometry), (height, width), transform=transform, dtype="uint8"),
          base, dtype="uint8", nodata=None)
    write(OUT / "city.tif", rasterize(((g, 1) for g in city.geometry), (height, width), transform=transform, dtype="uint8"),
          base, dtype="uint8", nodata=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
