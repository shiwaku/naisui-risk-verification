"""検証対象の自治体選びに使う元データを data/raw/ に取得する。

    uv run python scripts/download.py

取得するもの:
- 国土数値情報 雨水出水（内水）浸水想定区域 A51（2025年度版、収録22都道府県）
- 国土数値情報 行政区域 N03（2025年、A51 がある都道府県だけ）
- 水害履歴（浸水実績）の変換結果 sinsui_all.gpkg（ksj-suigai-rireki-converter）
- 国土数値情報 人口集中地区 A16（令和2年国勢調査、全47都道府県）

取得済みのファイルは飛ばす。
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

KSJ = "https://nlftp.mlit.go.jp/ksj/gml/data"

# A51-25 の配布ページ（KsjTmplt-A51-2025.html）に載っている都道府県コード。
# 静岡・山梨・大阪などは収録されていない。
A51_PREFS = [
    "01", "02", "04", "10", "11", "12", "13", "14", "16", "17", "18",
    "20", "23", "28", "31", "32", "33", "34", "35", "37", "38", "40",
]

SINSUI_URL = "https://shiwaku.github.io/ksj-suigai-rireki-converter/output/sinsui_all.gpkg"


def fetch(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.replace(dest)
    print(f"  {dest.relative_to(ROOT)} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def unzip(path: Path) -> Path:
    out = path.with_suffix("")
    if not out.exists():
        with zipfile.ZipFile(path) as z:
            z.extractall(out)
    return out


def main() -> int:
    print("A51 雨水出水（内水）浸水想定区域")
    for pref in A51_PREFS:
        unzip(fetch(f"{KSJ}/A51/A51-25/A51-25_{pref}_GML.zip", RAW / "A51" / f"A51-25_{pref}_GML.zip"))

    print("N03 行政区域")
    for pref in A51_PREFS:
        unzip(fetch(f"{KSJ}/N03/N03-2025/N03-20250101_{pref}_GML.zip", RAW / "N03" / f"N03-20250101_{pref}_GML.zip"))

    print("浸水実績")
    fetch(SINSUI_URL, RAW / "sinsui" / "sinsui_all.gpkg")

    print("A16 人口集中地区（令和2年）")
    for pref in (f"{i:02d}" for i in range(1, 48)):
        unzip(fetch(f"{KSJ}/A16/A16-20/A16-20_{pref}_GML.zip", RAW / "A16" / f"A16-20_{pref}_GML.zip"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
