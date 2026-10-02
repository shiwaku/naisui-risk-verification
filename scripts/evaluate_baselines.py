"""基準手法を A51（内水浸水想定区域）と比べる。docs/method-survey.md §7

    uv run python scripts/prepare_trial.py
    uv run python scripts/baseline_b0.py
    uv run python scripts/evaluate_baselines.py

評価する範囲: DID（令和2年）の中で、DEM の値があるセル。
正解: A51 の区域の中。浸水深の区分で3通りに分ける（全区分 / 0.3m以上 / 0.5m以上）。
鳥取市の A51 は7割が「0.3m未満」で、浅い区域が広く薄く広がっているため。

指標（スコアの大きい所から順に「危ない」とみなす）:
- PR-AUC（average precision）。ランダムなら正解の割合（prevalence）と同じ値になる
- capture@k: 上位 k% の面積に、正解の何割が入るか。lift = capture@k / k
- 面積をそろえた CSI: 推定の面積を正解の面積と同じにしたときの CSI。このとき precision = recall
二値の推定（窪地のマスク）は、precision・recall・CSI と推定の面積を出す。

同じスコアのセルが並ぶ所（窪地深 0 など）は、その中でランダムに選んだときの期待値で数える。

出力: output/tottori/baseline_metrics.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "interim" / "tottori"
OUT = ROOT / "output" / "tottori"

KS = [0.05, 0.10, 0.20]
# 正解の定義: 名前 → a51_class.tif の区分の下限（prepare_trial.py の DEPTH_CLASSES）
POSITIVES = {"全区分": 1, "0.3m以上": 2, "0.5m以上": 3}
ROUND = 0.01  # スコアを 1cm 単位に丸めて同順位をまとめる


def read(name: str) -> np.ndarray:
    with rasterio.open(WORK / name) as src:
        return src.read(1, masked=True).filled(np.nan).astype("float64") if src.dtypes[0].startswith("float") \
            else src.read(1)


def ranked_metrics(score: np.ndarray, pos: np.ndarray) -> dict:
    """スコアの大きい順に面積を積み上げたときの指標。同順位はまとめて線形に配分する。"""
    keys, inv = np.unique(np.round(score / ROUND).astype(np.int64), return_inverse=True)
    n_g = np.bincount(inv)[::-1].astype(float)  # 大きい順
    tp_g = np.bincount(inv, weights=pos)[::-1]
    cum_n, cum_tp = np.cumsum(n_g), np.cumsum(tp_g)
    N, P = cum_n[-1], cum_tp[-1]

    precision, recall = cum_tp / cum_n, cum_tp / P
    ap = float(np.sum(np.diff(np.concatenate([[0], recall])) * precision))

    def tp_at(area: float) -> float:
        i = int(np.searchsorted(cum_n, area))
        prev_n = cum_n[i - 1] if i else 0.0
        prev_tp = cum_tp[i - 1] if i else 0.0
        return prev_tp + (area - prev_n) * tp_g[i] / n_g[i]

    out = {"pr_auc": ap}
    for k in KS:
        cap = tp_at(k * N) / P
        out[f"capture@{k:.0%}"] = cap
        out[f"lift@{k:.0%}"] = cap / k
    tp = tp_at(P)
    out["csi_area_matched"] = tp / (2 * P - tp)
    return out


def binary_metrics(pred: np.ndarray, pos: np.ndarray) -> dict:
    tp = float(np.sum(pred & pos))
    fp, fn = float(np.sum(pred & ~pos)), float(np.sum(~pred & pos))
    return {
        "pred_km2": float(pred.sum()) / 1e6,
        "precision": tp / (tp + fp) if tp + fp else np.nan,
        "recall": tp / (tp + fn),
        "csi": tp / (tp + fp + fn),
    }


def main() -> int:
    if not (WORK / "b0_depth.tif").exists():
        print("先に scripts/baseline_b0.py を実行する", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    dem = read("dem_1m.tif")
    domain = (read("did.tif") == 1) & np.isfinite(dem)
    a51 = read("a51_class.tif")[domain]
    scores = {
        "標高だけ（低いほど危ない）": -dem[domain],
        "B0 窪地深": np.nan_to_num(read("b0_depth.tif")[domain]),
    }
    masks = {}
    for path in sorted(WORK.glob("b0_mask_*.tif")):
        d, a = path.stem.removeprefix("b0_mask_").split("_")
        masks[f"B0 窪地深≥{d[1:]}m・面積≥{a[1:]}m²"] = read(path.name)[domain] == 1

    rows = []
    N = domain.sum()
    for pos_name, min_cls in POSITIVES.items():
        pos = a51 >= min_cls
        P = pos.sum()
        print(f"評価範囲 {N / 1e6:.2f} km²、正解（A51 {pos_name}）{P / 1e6:.2f} km²（{P / N:.1%}）")
        base = {"positive": pos_name, "positive_km2": P / 1e6}
        rows.append({**base, "method": "ランダム", "pr_auc": P / N, **{f"capture@{k:.0%}": k for k in KS},
                     **{f"lift@{k:.0%}": 1.0 for k in KS}, "csi_area_matched": (P / N) / (2 - P / N)})
        rows += [{**base, "method": m, **ranked_metrics(s, pos)} for m, s in scores.items()]
        rows += [{**base, "method": m, **binary_metrics(s, pos)} for m, s in masks.items()]

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "baseline_metrics.csv", index=False, float_format="%.4f")
    print(f"  {(OUT / 'baseline_metrics.csv').relative_to(ROOT)}")
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(df.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
