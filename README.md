# naisui-risk-verification

内水ハザードマップが整備されていない地域について、公開されている地形データ（標高・地形分類）から
**内水氾濫が起こりやすい場所をどこまで推定できるか**を、浸水実績と既存の内水浸水想定区域を使って検証する。

調査の背景・データ・手法は [`docs/naisui-research-notes.md`](docs/naisui-research-notes.md) にまとめている。

## ビューワ

標高（Mapterhorn）、水害履歴（浸水実績）、地形分類（国土地理院）を1枚の地図に重ね、
「浸水した場所がどんな地形の上にあるか」を目で確かめるための Web ビューワ。

公開先（予定）: <https://shiwaku.github.io/naisui-risk-verification/app/>

| レイヤー | 内容 |
|---|---|
| 浸水実績 | 国土数値情報 水害履歴（1896〜2019年、14,585件）。成因（台風 / 大雨・その他）で塗り分け、イベント単位で絞り込める |
| 地形分類 | 国土地理院 ベクトルタイル提供実験（地形分類）の自然地形・人工地形。**内水に関係が深い分類だけ**に絞って表示できる |
| 標高 | Mapterhorn の地形タイル（基盤地図情報 DEM を含む）。段彩（0〜5m まで狭められる）・陰影起伏・等高線・3D地形 |

使い方・設計上の判断は [`viewer/README.md`](viewer/README.md) を参照。

```sh
cd viewer
npm install
npm run dev      # http://localhost:5175
npm run build    # 検証を通してから ../app/ へビルド
```

## 前提と限界

- 本手法は内水氾濫の「起こりやすさの目安」であり、正式な内水浸水想定区域の代わりにはならない。
- 下水道の能力、ポンプ場、雨水貯留施設、道路の縁石・建物・塀による流れの変化は考慮していない。
- DEM の誤差（数十cm）と測量時期、地形分類の作成時期によって、現在の地形と合わない場合がある。
- 浸水実績は内水と外水が混在しており、小規模な内水浸水は記録されていない可能性が高い。
- 地形分類データは国土地理院の「提供実験」であり、基本測量成果ではない。

## 出典

- 浸水実績: [国土数値情報（水害履歴・浸水実績）国土交通省](https://nlftp.mlit.go.jp/ksj/) を加工して作成（変換: [shiwaku/ksj-suigai-rireki-converter](https://github.com/shiwaku/ksj-suigai-rireki-converter)）
- 地形分類: [国土地理院 ベクトルタイル提供実験（地形分類）](https://github.com/gsi-cyberjapan/experimental_landformclassification)（[解説](https://www.gsi.go.jp/bousaichiri/lfc_index.html)）。[国土地理院コンテンツ利用規約](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html)に従って利用
- 標高: [Mapterhorn](https://mapterhorn.com/)（[attribution](https://mapterhorn.com/attribution)）
- 背景地図: [国土地理院 最適化ベクトルタイル](https://github.com/gsi-cyberjapan/optimal_bvmap) / [地理院タイル](https://maps.gsi.go.jp/development/ichiran.html)

本リポジトリは個人が作成するものであり、国土交通省・国土地理院の公式なものではない。

## ライセンス

[MIT](LICENSE)。ビューワの段彩のピクセル走査は[全国Ｑ地図](https://github.com/qchizu/qchizu_maplibre)（MIT license, Copyright 2024 全国Ｑ地図管理者）に由来する（`viewer/src/relief.ts` 冒頭に表示）。
データの利用条件は各出典に従う。
