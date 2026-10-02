"""段階1の試行（鳥取市）の確認用の図を作る。

    uv run python scripts/baseline_b0.py
    uv run python scripts/plot_trial.py

出力（output/tottori/）:
- big_depressions.png  B0（fill）で面積の大きい窪地の上位12と、A51・DID
- b0_vs_b0b.png        B0（fill）と B0b（掘り抜き 20m）の窪地深 ≥0.1m の比較
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import numpy as np
import rasterio
from scipy import ndimage

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "interim" / "tottori"
OUT = ROOT / "output" / "tottori"

# 日本語フォントのうち、入っているものを使う
_installed = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in ["Yu Gothic", "Hiragino Sans", "Noto Sans CJK JP"] if f in _installed] or ["sans-serif"]
DPI = 80
N_BIG = 12
BREACH_M = 20


def read(name: str) -> np.ndarray:
    with rasterio.open(WORK / name) as src:
        return src.read(1)


def hillshade(dem: np.ndarray, cell: float) -> np.ndarray:
    gy, gx = np.gradient(np.nan_to_num(dem), cell)
    return np.clip(0.5 + (gy - gx) * 0.7 / np.sqrt(1 + gx**2 + gy**2) * 1.5, 0, 1)


def outline(ax, mask: np.ndarray, **kw) -> None:
    ax.contour(mask.astype(float), levels=[0.5], **kw)


def big_depressions(dem, depth, a51, did) -> None:
    step = 5
    lab, _ = ndimage.label(depth >= 0.1, structure=np.ones((3, 3)))
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    big = np.argsort(sizes)[::-1][:N_BIG]
    rank = np.zeros(sizes.size, int)
    rank[big] = np.arange(1, N_BIG + 1)
    r = rank[lab[::step, ::step]]

    fig, ax = plt.subplots(figsize=(14, 12), dpi=DPI)
    d = dem[::step, ::step]
    ax.imshow(hillshade(d, step), cmap="gray", vmin=0, vmax=1)
    ax.imshow(np.ma.masked_invalid(d), cmap="terrain", vmin=0, vmax=60, alpha=0.35)
    ax.imshow(np.ma.masked_equal(r, 0), cmap="tab20", alpha=0.55, interpolation="nearest")
    outline(ax, a51[::step, ::step] > 0, colors="blue", linewidths=0.6)
    outline(ax, a51[::step, ::step] >= 3, colors="red", linewidths=0.8)
    outline(ax, did[::step, ::step] == 1, colors="black", linewidths=1.2, linestyles="--")
    for i in range(1, N_BIG + 1):
        cy, cx = ndimage.center_of_mass(r == i)
        ax.text(cx, cy, str(i), fontsize=14, weight="bold", ha="center", bbox=dict(fc="w", alpha=0.7))
    ax.set_title(f"B0 の大きな窪地（上位{N_BIG}、色）・A51（青: 全区分、赤: 0.5m以上）・DID（黒破線）")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(OUT / "big_depressions.png")
    plt.close(fig)


def fill_vs_breach(dem, depth, breached, a51, did) -> None:
    step, pad = 4, 300
    ys, xs = np.where(did == 1)
    sl = (slice(ys.min() - pad, ys.max() + pad, step), slice(xs.min() - pad, xs.max() + pad, step))
    hs = hillshade(dem[sl], step)
    fig, axs = plt.subplots(1, 2, figsize=(20, 10), dpi=DPI)
    for ax, x, title in [(axs[0], depth, "B0（fill）"), (axs[1], breached, f"B0b（掘り抜き {BREACH_M}m）")]:
        ax.imshow(hs, cmap="gray")
        ax.imshow(np.ma.masked_less(x[sl], 0.1), cmap="YlOrRd", vmin=0, vmax=2, alpha=0.8, interpolation="nearest")
        outline(ax, a51[sl] >= 3, colors="blue", linewidths=0.8)
        outline(ax, did[sl] == 1, colors="black", linewidths=1.2, linestyles="--")
        ax.set_title(f"{title}: 窪地深 ≥0.1m（黄〜赤、2m で頭打ち）・A51 0.5m以上（青）・DID（破線）")
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(OUT / "b0_vs_b0b.png")
    plt.close(fig)


def main() -> int:
    breached_name = f"b0b_depth_{BREACH_M}m.tif"
    if not (WORK / breached_name).exists():
        print("先に scripts/baseline_b0.py を実行する", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    dem = read("dem_1m.tif").astype("float32")
    dem[dem < -9000] = np.nan
    depth = np.nan_to_num(read("b0_depth.tif"))
    a51, did = read("a51_class.tif"), read("did.tif")
    big_depressions(dem, depth, a51, did)
    fill_vs_breach(dem, depth, np.nan_to_num(read(breached_name)), a51, did)
    for name in ["big_depressions.png", "b0_vs_b0b.png"]:
        print(f"  {(OUT / name).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
