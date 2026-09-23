"""都市型水害（都市部の内水被害）の棟数ランキングを作る。

    uv run python scripts/select_urban_naisui.py    # 先に市区町村ごとの判定を作る
    uv run python scripts/rank_urban_naisui.py

出力:
- output/urban_naisui_ranking.csv   都市型水害の発生地の全件（棟数の多い順）
- ranking/index.html                GitHub Pages で公開する表（全件、並べ替え・絞り込みつき）
- docs/urban-naisui-ranking.md      上位 TOP_N の表

政令市は、水害統計が年によって区で書いたり市でまとめて書いたりするので、区と市の記録を
足し合わせて市全体で1行にする（同じ市が二重に並ばないように）。区の内訳は備考に書く。
都市部かどうか・棟数の基準（select_urban_naisui.py と同じ）は、市全体に対して判定し直す。

付ける列:
- 異常気象の内訳: 台風 / 梅雨前線 / 豪雨・その他 / その他（融雪・高潮など）の棟数の割合
- 宅地の割合: 浸水面積（宅地その他＋農地）のうち宅地その他の割合
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from select_urban_naisui import MIN_BUILDINGS, PREFS, URBAN_DID_POP_PCT  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
DOC = ROOT / "docs" / "urban-naisui-ranking.md"
HTML = ROOT / "ranking" / "index.html"
TEMPLATE = Path(__file__).resolve().parent / "templates" / "ranking.html"

TOP_N = 50
WARD = r"^(.+市)(.+区)$"
EVENT_COLS = {
    "typhoon": "buildings_台風",
    "tsuyu": "buildings_梅雨前線",
    "gou": "buildings_豪雨・その他",
    "etc": "buildings_その他",
}


def build() -> pd.DataFrame:
    t = pd.read_csv(OUT / "urban_naisui_municipalities.csv", dtype={"code": str})
    t = t[t["code"].notna()].copy()  # DID のない町村は都市部ではない

    # 政令市の区を市にまとめる。区の行にも市の行にも同じ市名を付ける
    m = t["muni"].str.extract(WARD)
    t["city"] = m[0].fillna(t["muni"])
    t["ward"] = m[1]
    is_seirei = t.groupby(["pref", "city"])["ward"].transform(lambda s: s.notna().any())
    t["unit"] = t["muni"].where(~is_seirei, t["city"])

    # 市全体の DID 人口割合は、select_urban_naisui.py が作った市の行（区を足し上げた値）を使う
    did_pct = t[t["ward"].isna()].set_index(["pref", "unit"])["did_pop_pct"]

    def wards_note(g: pd.DataFrame) -> str:
        w = g[g["ward"].notna()].sort_values("buildings", ascending=False)
        return "、".join(f"{r.ward} {r.buildings:,.0f}" for r in w.head(4).itertuples()) + ("…" if len(w) > 4 else "")

    rows = []
    for (pref, unit), g in t.groupby(["pref", "unit"]):
        b = g["buildings"].sum()
        area = g["area_km2"].sum()
        row = {
            "pref": pref,
            "pref_code": PREFS.index(pref) + 1,
            "muni": unit,
            "did_pop_pct": float(did_pct.get((pref, unit), g["did_pop_pct"].max())),
            "yukaue": float(g["yukaue"].sum()),
            "yukashita": float(g["yukashita"].sum()),
            "buildings": float(b),
            "takuchi_share": float(g["area_takuchi_km2"].sum() / area) if area > 0 else None,
            "first_year": int(g["first_year"].min()),
            "last_year": int(g["last_year"].max()),
            "years": int(g["years"].max()),  # 区ごとの年数の最大（区をまたいだ年数の和ではない）
            "has_a51": bool(g["has_a51"].any()),
            "hires_dem_pref": bool(g["hires_dem_pref"].any()),
            "wards": wards_note(g) if g["ward"].notna().any() else "",
        }
        for key, col in EVENT_COLS.items():
            row[f"{key}_share"] = float(g[col].sum() / b) if b > 0 else 0.0
        rows.append(row)
    r = pd.DataFrame(rows)
    r = r[(r["did_pop_pct"] >= URBAN_DID_POP_PCT) & (r["buildings"] >= MIN_BUILDINGS)]
    r = r.sort_values("buildings", ascending=False).reset_index(drop=True)
    r.insert(0, "rank", r.index + 1)
    return r


def write_html(r: pd.DataFrame) -> None:
    data = json.loads(r.to_json(orient="records", force_ascii=False))
    html = (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        .replace("__URBAN_PCT__", f"{URBAN_DID_POP_PCT:.0f}")
        .replace("__MIN_BUILDINGS__", str(MIN_BUILDINGS))
        .replace("__GENERATED__", date.today().isoformat())
    )
    HTML.parent.mkdir(exist_ok=True)
    HTML.write_text(html, encoding="utf-8", newline="\n")


def write_md(r: pd.DataFrame) -> None:
    yes = lambda b: "○" if b else ""  # noqa: E731
    p = lambda x: "–" if x is None or pd.isna(x) else f"{x * 100:.0f}%"  # noqa: E731
    lines = [
        "# 都市型水害（内水）の棟数ランキング",
        "",
        "Web 版（全件、並べ替え・絞り込みつき）: <https://shiwaku.github.io/naisui-risk-verification/ranking/>",
        "",
        "集計: `scripts/rank_urban_naisui.py`（全件は `output/urban_naisui_ranking.csv`）",
        "関連: [検証対象地域の選定](study-area-selection.md) §4",
        "",
        f"2010〜2023年に、**都市部**（人口集中地区に住む人が {URBAN_DID_POP_PCT:.0f}% 以上）で、"
        f"**内水・窪地内水による床上＋床下の浸水が {MIN_BUILDINGS} 棟以上**あった市区町村の、上位 {TOP_N}。"
        f"該当は全部で {len(r)}。",
        "",
        "- 出典: 国土交通省「水害統計調査」一般資産等水害統計基本表（e-Stat）、国土数値情報 人口集中地区（A16、令和2年）・"
        "雨水出水浸水想定区域（A51、2025年度版）",
        "- 政令市は区と市の記録を足し合わせ、市全体で1行にした。区の内訳（棟数の多い順）を備考に書いた",
        "- 「台風」「梅雨前線」「豪雨・その他」は、異常気象名で分けた棟数の割合。「台風○号及び豪雨」のように混ざる名前は台風に入れた。"
        "局地的な短時間強雨は「豪雨・その他」に入ることが多い",
        "- 「宅地の割合」は、浸水面積（宅地その他＋農地）のうち宅地その他の割合",
        "- 「年数」は被害の記録があった年の数（政令市は区ごとの最大）",
        "- 「A51」は内水浸水想定区域が国土数値情報に収録されているか",
        "- 「県の高解像度標高」は、市街地を覆う都道府県の LP の DEM・DSM・点群がある**都道府県**か"
        "（[標高データの候補](elevation-sources.md) §2。市区町村ごとの被覆は未確認）",
        "- 水害統計の「内水」には、河川の水位が上がって排水できなくなった内水も含まれる。短時間強雨による内水だけではない",
        "",
        "| 順位 | 都道府県 | 市区町村 | 床上 | 床下 | 合計（棟） | 台風 | 梅雨前線 | 豪雨・その他 | 宅地の割合 | 年数 | 期間 | DID 人口割合 | A51 | 県の高解像度標高 | 備考（政令市の区の内訳） |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|:---:|:---:|---|",
    ]
    for x in r.head(TOP_N).itertuples():
        lines.append(
            f"| {x.rank} | {x.pref} | {x.muni} | {x.yukaue:,.0f} | {x.yukashita:,.0f} | {x.buildings:,.0f} | "
            f"{p(x.typhoon_share)} | {p(x.tsuyu_share)} | {p(x.gou_share)} | {p(x.takuchi_share)} | "
            f"{x.years} | {x.first_year if x.first_year == x.last_year else f'{x.first_year}〜{x.last_year}'} | {x.did_pop_pct:.1f}% | {yes(x.has_a51)} | "
            f"{yes(x.hires_dem_pref)} | {x.wards} |"
        )
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    r = build()
    r.to_csv(OUT / "urban_naisui_ranking.csv", index=False, encoding="utf-8-sig")
    write_html(r)
    write_md(r)
    print(f"{len(r)} 件 → {HTML.relative_to(ROOT)}、{DOC.relative_to(ROOT)}（上位 {TOP_N}）")
    cols = ["rank", "pref", "muni", "buildings", "typhoon_share", "tsuyu_share", "gou_share", "takuchi_share"]
    with pd.option_context("display.width", 200, "display.float_format", "{:.2f}".format):
        print(r.head(25)[cols].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
