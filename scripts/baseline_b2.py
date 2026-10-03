"""基準手法 B2: TWI と HAND（それぞれ単独）。docs/method-survey.md §6.2

    uv run python scripts/prepare_trial.py
    uv run python scripts/baseline_b2.py

水の流れは、B0b と同じく窪地を BREACH_M 掘り抜いてから埋めた DEM で計算する（D8）。
- TWI（地形湿潤指数）= ln(比集水面積 / tanβ)。大きいほど水が集まりやすい。WhiteboxTools WetnessIndex
- HAND（最寄りの流路からの高さ）。集水面積が STREAM_KM2 以上のセルを流路とし、
  そこへ流れ下る先の流路との標高差。小さいほど危ない。WhiteboxTools ElevationAboveStream

出力（data/interim/tottori/）:
- b2_twi.tif               TWI
- b2_hand_{面積}km2.tif    HAND（m）
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio
from whitebox import WhiteboxTools

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "interim" / "tottori"

BREACH_M = 20
# 流路とみなす集水面積（km²）。0.1 は街区の排水路、1 は中小河川くらい
STREAM_KM2 = [0.1, 1.0]


def run(ok: int, name: str) -> None:
    if ok != 0:
        raise RuntimeError(f"WhiteboxTools {name} に失敗した")


def save_compressed(src_path: Path, dst_path: Path, profile: dict) -> None:
    """WhiteboxTools の出力は非圧縮で大きいので、圧縮して書き直す。"""
    with rasterio.open(src_path) as src:
        a = src.read(1, masked=True).filled(np.nan).astype("float32")
    with rasterio.open(dst_path, "w", **(profile | dict(dtype="float32", nodata=np.nan))) as dst:
        dst.write(a, 1)
    print(f"  {dst_path.name}")


def main() -> int:
    dem_path = WORK / "dem_1m.tif"
    if not dem_path.exists():
        print("先に scripts/prepare_trial.py を実行する", file=sys.stderr)
        return 1
    with rasterio.open(dem_path) as src:
        profile = src.profile
        cell = src.transform.a

    wbt = WhiteboxTools()
    wbt.set_verbose_mode(False)
    tmp = {k: WORK / f"_b2_{k}.tif" for k in ["hydro", "sca", "slope", "twi", "acc", "streams", "hand"]}
    try:
        run(wbt.breach_depressions_least_cost(str(dem_path), str(tmp["hydro"]), dist=int(BREACH_M / cell), fill=True),
            "BreachDepressionsLeastCost")

        run(wbt.d8_flow_accumulation(str(tmp["hydro"]), str(tmp["sca"]), out_type="specific contributing area"),
            "D8FlowAccumulation")
        run(wbt.slope(str(tmp["hydro"]), str(tmp["slope"]), units="degrees"), "Slope")
        run(wbt.wetness_index(str(tmp["sca"]), str(tmp["slope"]), str(tmp["twi"])), "WetnessIndex")
        save_compressed(tmp["twi"], WORK / "b2_twi.tif", profile)

        run(wbt.d8_flow_accumulation(str(tmp["hydro"]), str(tmp["acc"]), out_type="catchment area"),
            "D8FlowAccumulation")
        for km2 in STREAM_KM2:
            run(wbt.extract_streams(str(tmp["acc"]), str(tmp["streams"]), threshold=km2 * 1e6), "ExtractStreams")
            run(wbt.elevation_above_stream(str(tmp["hydro"]), str(tmp["streams"]), str(tmp["hand"])),
                "ElevationAboveStream")
            save_compressed(tmp["hand"], WORK / f"b2_hand_{km2:g}km2.tif", profile)
    finally:
        for p in tmp.values():
            p.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
