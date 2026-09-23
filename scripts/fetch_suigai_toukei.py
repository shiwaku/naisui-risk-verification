"""水害統計調査の「一般資産等水害統計基本表」を e-Stat から取得する。

    uv run python scripts/fetch_suigai_toukei.py [開始年] [終了年]   # 既定 2010 2024

1行が「都道府県 × 異常気象（発生年月）× 河川・海岸 × 市区町村 × 水害原因」の水害の記録で、
水害区域面積（宅地その他・農地・地下）と被災家屋棟数（床下・床上・半壊・全壊）が入っている。
水害原因に「内水」「窪地内水」があり、市町村ごとの内水被害を全国で比べられる。

e-Stat の「ファイル」から年ごとの Excel を取る（API のアプリケーション ID は不要）。
基本表の表番号は年によって違うので、各年の「水害統計基本表」の分類にあるファイルを取り、
見出しに「水害原因」「市区町村名」「床上」があるものを一般資産等の基本表とみなす。

出典: 国土交通省「水害統計調査」（e-Stat、政府統計コード 00600590）
"""

from __future__ import annotations

import html
import re
import sys
import time
from pathlib import Path

import openpyxl
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "suigai_toukei"

BASE = "https://www.e-stat.go.jp"
TOUKEI = "00600590"

# 調査年 → e-Stat の tstat（ファイル一覧の年の分類）。一覧ページから取れるが、並びが崩れた時に
# 気付けるよう、取れた値を年と突き合わせて使う。
WAREKI = {"平成": 1988, "令和": 2018}
KANJI_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def get(url: str) -> str:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    time.sleep(0.5)  # e-Stat への負荷を抑える
    return r.text


def survey_years() -> dict[int, str]:
    s = get(f"{BASE}/stat-search/files?page=1&toukei={TOUKEI}")
    years: dict[int, str] = {}
    for tstat, label in re.findall(r'tstat=(\d{12})[^"]*"[^>]*>(?:\s|<[^>]+>)*([^<]*年水害統計調査)', s):
        m = re.match(r"(平成|令和)(元|[０-９\d]+)年", html.unescape(label).strip().translate(KANJI_DIGITS))
        if not m:
            continue
        n = 1 if m.group(2) == "元" else int(m.group(2))
        years[WAREKI[m.group(1)] + n] = tstat
    return years


def basic_table_files(tstat: str) -> list[str]:
    """その年の「水害統計基本表」分類にある Excel の statInfId。"""
    s = get(f"{BASE}/stat-search/files?page=1&toukei={TOUKEI}&tstat={tstat}")
    # 分類のリンク文字列は一覧ページに出ないことがあるので、分類ページの <title> で見分ける
    ids: list[str] = []
    for c in sorted(set(re.findall(r"tclass1=(\d{12})", s))):
        page = get(
            f"{BASE}/stat-search/files?page=1&toukei={TOUKEI}&tstat={tstat}&cycle=7"
            f"&tclass1={c}&layout=datalist&tclass2val=0"
        )
        title = re.search(r"<title>(.*?)</title>", page, re.S)
        if title and "基本表" in html.unescape(title.group(1)):
            ids += re.findall(r"file-download\?statInfId=(\d+)&amp;fileKind=0", page)
    return sorted(set(ids))


def is_general_asset_table(path: Path) -> bool:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        head = " ".join(
            str(v) for row in ws.iter_rows(min_row=1, max_row=6, values_only=True) for v in row if v is not None
        )
    finally:
        wb.close()
    return all(k in head for k in ("水害原因", "市区町村名", "床")) and "河川等種別" in head


def main(start: int, end: int) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    years = survey_years()
    for year in range(start, end + 1):
        dest = OUT / f"kihon_{year}.xlsx"
        if dest.exists():
            print(f"{year}: 取得済み")
            continue
        if year not in years:
            print(f"{year}: e-Stat に年報が見つからない")
            continue
        found = False
        for sid in basic_table_files(years[year]):
            tmp = OUT / f"_{year}_{sid}.xlsx"
            r = requests.get(f"{BASE}/stat-search/file-download?statInfId={sid}&fileKind=0", timeout=120)
            r.raise_for_status()
            tmp.write_bytes(r.content)
            time.sleep(0.5)
            try:
                ok = is_general_asset_table(tmp)
            except Exception:  # xls など読めない形式
                ok = False
            if ok and not found:
                tmp.replace(dest)
                found = True
                print(f"{year}: {dest.name}（statInfId={sid}）")
            else:
                tmp.unlink()
        if not found:
            print(f"{year}: 一般資産等の基本表が見つからない")
    return 0


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:3]]
    sys.exit(main(*(args or [2010, 2024])))
