"""水害統計の基本表から、市区町村ごとの内水被害を集計する。

    uv run python scripts/fetch_suigai_toukei.py      # 先に基本表を取得
    uv run python scripts/aggregate_suigai_naisui.py

出力:
- output/suigai_naisui_records.csv   内水・窪地内水の記録（1行1記録、年つき）
- output/suigai_naisui_by_muni.csv   市区町村ごとの集計

基本表は年によって書き方が違う（2010年は都道府県・異常気象・水系が1列目に字下げで入り、
2014年は1列ずれ、2015年以降は平らに並ぶ）。ただし「水害原因」の列から右の数値の並びは
どの年も同じなので、見出し行で「市区町村名」「水害原因」の列を探し、そこからの位置で読む。
「〃」は上の行と同じ値、「合計」は小計の行なので除く。

異常気象名は、1つの異常気象の最初の行にだけ書かれる（下の行は空欄か「〃」）ので、上の行から引き継ぐ。
名前に含まれる語で、次の区分に分ける（「台風○号及び豪雨」のように複数が混ざる名前は台風に入れる）。
- 台風: 「台風」を含む
- 梅雨前線: 「梅雨」を含む
- 豪雨・その他: 「豪雨」「その他の異常気象」など（局地的な短時間強雨はここに入ることが多い）
- その他: 融雪・高潮・波浪
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "suigai_toukei"
OUT = ROOT / "output"

NAISUI_CAUSES = {"内水", "窪地内水"}

# 「水害原因」の列から右への位置（どの年も同じ並び）
OFFSETS = {
    "area_takuchi_m2": 1,   # 水害区域面積 宅地その他
    "area_nouchi_m2": 2,    # 農地
    "area_m2": 3,           # 計
    "area_chika_m2": 4,     # 地下
    "yukashita": 5,         # 床下浸水（棟）
    "yukaue_1_49": 6,       # 床上浸水 1〜49cm
    "yukaue_50_99": 7,      # 50〜99cm
    "yukaue_100": 8,        # 100cm 以上
    "yukaue": 9,            # 床上浸水 計
    "hankai": 10,           # 半壊
    "zenkai": 11,           # 全壊・流失
}

PREFS = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県",
    "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]


# 2014年以前の表は都道府県名を「大阪」「神奈川」のように府・県を付けずに書く
PREF_BY_SHORT = {p if p == "北海道" else p[:-1]: p for p in PREFS}
PREF_BY_SHORT.update({p: p for p in PREFS})

EVENT_WORDS = re.compile(r"台風|豪雨|梅雨|前線|異常気象|低気圧|大雨|融雪|高潮|波浪|降雨|雷雨")


def event_type(name: str) -> str:
    if "台風" in name:
        return "台風"
    if "梅雨" in name:
        return "梅雨前線"
    if re.search(r"融雪|高潮|波浪", name) and not re.search(r"豪雨|大雨|降雨", name):
        return "その他"
    return "豪雨・その他"


# 改ページごとに繰り返される見出しの文字列。市区町村として数えない
HEADER_WORDS = {"市区町村名", "都道府県名", "水害原因"}


def clean(v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return re.sub(r"\s+", "", str(v).replace("　", ""))


def to_num(v: object) -> float:
    s = clean(v).replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def read_year(path: Path, year: int) -> pd.DataFrame:
    df = pd.read_excel(path, header=None, sheet_name=0, dtype=object)
    head = next(i for i in range(12) if any(clean(v) == "水害原因" for v in df.iloc[i]))
    cols = [clean(v) for v in df.iloc[head]]
    c_muni, c_cause = cols.index("市区町村名"), cols.index("水害原因")
    # 「異常気象名」の見出しは「水害原因」と同じ行とは限らない（2010年は1列目の2行目）
    c_event = next(
        j for i in range(max(0, head - 2), head + 4) for j, v in enumerate(df.iloc[i]) if clean(v) == "異常気象名"
    )

    records = []
    pref = muni = event = ""
    for _, row in df.iloc[head + 1 :].iterrows():
        cells = [clean(v) for v in row.tolist()]
        # 都道府県は「水害原因」より左のどこかに現れる（年によって列が違う）。現れたら以降に引き継ぐ
        for v in cells[:c_cause]:
            if v in PREF_BY_SHORT:
                pref = PREF_BY_SHORT[v]
                break
        ev = cells[c_event]
        if ev and ev != "異常気象名" and EVENT_WORDS.search(ev):
            event = ev
        m, cause = cells[c_muni], cells[c_cause]
        if m and m != "〃" and m not in HEADER_WORDS:
            muni = m
        if cause not in NAISUI_CAUSES or muni in ("", "合計") or not pref:
            continue
        rec = {"year": year, "pref": pref, "muni": muni, "cause": cause, "event": event, "event_type": event_type(event)}
        rec.update({k: to_num(row.iloc[c_cause + o]) for k, o in OFFSETS.items()})
        records.append(rec)
    return pd.DataFrame(records)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    frames = []
    for path in sorted(RAW.glob("kihon_*.xls*")):
        year = int(re.search(r"kihon_(\d{4})", path.name).group(1))
        d = read_year(path, year)
        print(f"{year}: 内水・窪地内水の記録 {len(d)} 件、床上 {d['yukaue'].sum():.0f} 棟、床下 {d['yukashita'].sum():.0f} 棟")
        frames.append(d)
    rec = pd.concat(frames, ignore_index=True)
    rec.to_csv(OUT / "suigai_naisui_records.csv", index=False, encoding="utf-8-sig")

    g = rec.groupby(["pref", "muni"])
    by = g.agg(
        records=("year", "size"),
        years=("year", "nunique"),
        first_year=("year", "min"),
        last_year=("year", "max"),
        area_takuchi_km2=("area_takuchi_m2", lambda s: s.sum() / 1e6),
        yukaue=("yukaue", "sum"),
        yukashita=("yukashita", "sum"),
        kubochi_records=("cause", lambda s: int((s == "窪地内水").sum())),
    )
    by["buildings"] = by["yukaue"] + by["yukashita"]
    by["area_km2"] = g["area_m2"].sum() / 1e6
    # 異常気象の区分ごとの床上＋床下の棟数
    rec["b"] = rec["yukaue"] + rec["yukashita"]
    per_type = rec.pivot_table(index=["pref", "muni"], columns="event_type", values="b", aggfunc="sum", fill_value=0)
    for t in ("台風", "梅雨前線", "豪雨・その他", "その他"):
        by[f"buildings_{t}"] = per_type[t] if t in per_type else 0.0
    rec = rec.drop(columns="b")
    by = by.sort_values("buildings", ascending=False)
    by[["area_takuchi_km2", "area_km2"]] = by[["area_takuchi_km2", "area_km2"]].round(3)
    by.to_csv(OUT / "suigai_naisui_by_muni.csv", encoding="utf-8-sig")

    print(f"\n{rec['year'].min()}〜{rec['year'].max()}年、内水被害のある市区町村 {len(by)}")
    with pd.option_context("display.max_rows", 40, "display.width", 200):
        print(by.head(40).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
