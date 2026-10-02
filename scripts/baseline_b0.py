"""基準手法 B0: 窪地深（fill 差分）。docs/method-survey.md §6.2

    uv run python scripts/prepare_trial.py
    uv run python scripts/baseline_b0.py

DEM の窪地を埋め（WhiteboxTools FillDepressions、Wang & Liu 2006）、埋めた深さ = 埋めた後の標高 − 元の標高
を窪地深とする。雨量は使わない。

B0b: 掘り抜いてから埋める（WhiteboxTools BreachDepressionsLeastCost、Lindsay 2016）。
DEM には道路・堤防の下を通る水路や樋門が表れず、堤防に囲まれた低地が丸ごと窪地になる
（docs/trial-tottori.md §5）。窪地の出口を最大 BREACH_DISTS m まで最小コストで掘り抜き、
抜けきらない窪地だけを埋めて、その深さを窪地深とする。距離は1つに決めず掃引する。

出力（data/interim/tottori/）:
- filled_1m.tif         窪地を埋めた標高
- b0_depth.tif          窪地深（m）。評価ではこの値の大きい順に「危ない」とみなす
- b0_mask_d{深さ}_a{面積}.tif  窪地深が MIN_DEPTH 以上のセルが、つながって MIN_AREA m² 以上のまとまりになる所を 1
- b0b_depth_{距離}m.tif  B0b の窪地深（m）
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from whitebox import WhiteboxTools

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "interim" / "tottori"

# 窪地とみなす深さ（A51 は 0.1m 未満を区域にしない）と、まとまりの面積の下限
MIN_DEPTH = 0.1
MIN_AREAS = [0, 100, 1000]
# B0b で掘り抜く最大距離（m）
BREACH_DISTS = [10, 20, 30, 50, 100]


def main() -> int:
    dem_path, filled_path = WORK / "dem_1m.tif", WORK / "filled_1m.tif"
    if not dem_path.exists():
        print("先に scripts/prepare_trial.py を実行する", file=sys.stderr)
        return 1

    if not filled_path.exists():
        wbt = WhiteboxTools()
        wbt.set_verbose_mode(False)
        rc = wbt.fill_depressions(str(dem_path), str(filled_path), fix_flats=False)
        if rc != 0 or not filled_path.exists():
            print("FillDepressions に失敗した", file=sys.stderr)
            return 1

    with rasterio.open(dem_path) as src:
        dem = src.read(1, masked=True)
        profile = src.profile
    with rasterio.open(filled_path) as src:
        filled = src.read(1, masked=True)

    depth = (filled - dem).filled(np.nan).astype("float32")
    depth[depth < 0] = 0  # 丸め誤差
    with rasterio.open(WORK / "b0_depth.tif", "w", **(profile | dict(nodata=np.nan))) as dst:
        dst.write(depth, 1)
    valid = np.isfinite(depth)
    print(f"  b0_depth.tif: 窪地深 > 0 のセル {np.mean(depth[valid] > 0):.1%}、"
          f"≥{MIN_DEPTH}m {np.mean(depth[valid] >= MIN_DEPTH):.1%}")

    deep = np.nan_to_num(depth) >= MIN_DEPTH
    labels, n = ndimage.label(deep, structure=np.ones((3, 3)))
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    for min_area in MIN_AREAS:
        keep = sizes >= min_area / (profile["transform"].a ** 2)
        keep[0] = False
        mask = keep[labels].astype("uint8")
        name = f"b0_mask_d{MIN_DEPTH:g}_a{min_area}.tif"
        with rasterio.open(WORK / name, "w", **(profile | dict(dtype="uint8", nodata=None, predictor=1))) as dst:
            dst.write(mask, 1)
        print(f"  {name}: まとまり {int(keep.sum()):,} 個、{mask.sum() / 1e6:.2f} km²")

    wbt = WhiteboxTools()
    wbt.set_verbose_mode(False)
    for dist in BREACH_DISTS:
        out = WORK / f"b0b_depth_{dist}m.tif"
        if out.exists():
            continue
        tmp = WORK / f"breached_{dist}m.tif"
        rc = wbt.breach_depressions_least_cost(str(dem_path), str(tmp), dist=int(dist / profile["transform"].a), fill=True)
        if rc != 0 or not tmp.exists():
            print(f"BreachDepressionsLeastCost（{dist}m）に失敗した", file=sys.stderr)
            return 1
        with rasterio.open(tmp) as src:
            d = np.clip((src.read(1, masked=True) - dem).filled(np.nan), 0, None).astype("float32")
        tmp.unlink()  # 非圧縮で大きいので消す
        with rasterio.open(out, "w", **(profile | dict(nodata=np.nan))) as dst:
            dst.write(d, 1)
        print(f"  {out.name}: ≥{MIN_DEPTH}m {np.mean(d[np.isfinite(d)] >= MIN_DEPTH):.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
