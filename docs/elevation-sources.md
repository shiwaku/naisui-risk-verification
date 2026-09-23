# 標高データの候補（都道府県のオープンデータ）

調査日: 2026-09-23
関連: [手法選定](method-survey.md) §6・§8

推定の元データとする標高は、国土地理院の基盤地図情報 DEM（5m / 1m）より、
**都道府県が [G空間情報センター](https://www.geospatial.jp/) で公開している航空レーザ測量（LP）の DEM・DSM・点群**を優先する。

## 1. 優先する理由

- **解像度が高い。**
  - 0.5m や 0.25m のグリッドが多い。
  - 5m DEM では表せない道路の縁石・路面の高まり、細い水路、小さなアンダーパスが出る。内水は道路を伝って広がることが多い。
- **DSM や点群がある。**
  - 建物を含む表面の高さが取れる。
  - DEM5A は建物を取り除いた地表面なので、建物が水を止めない（[手法選定](method-survey.md) §8）。DSM − DEM から建物の範囲を作れば、建物を障害物として扱える。
- **利用条件が扱いやすい。**
  - CC BY 4.0 などのオープンライセンスで公開されているものが多い。
  - 公開リポジトリで取得スクリプトから再現する形にしやすい。
  - 測量法の承認申請が要るかどうかは、データごとの利用規約で確かめる（下表の「ライセンス」）。
- **計測が新しい。**
  - 2019〜2025年度の計測が中心で、基盤地図情報 DEM より新しい地域が多い。

## 2. 候補の一覧

内水浸水想定区域がある市町村（[重ねるハザードマップの掲載65市町村](https://disaportal.gsi.go.jp/hazardmapportal/hazardmap/copyright/naisui.html)）と重なるものを中心に並べた。
「市街地」の列は、市町村の中心でタイルやデータの有無を確かめた結果である（2026-09-23）。

| 都道府県 | データ | 解像度・形式 | 市街地 | ライセンス | 内水浸水想定区域がある市町村 |
|---|---|---|---|---|---|
| 東京都 | [多摩地域点群](https://www.geospatial.jp/ckan/dataset/tokyopc-tama-2023)、[区部点群](https://www.geospatial.jp/ckan/dataset/tokyopc-23ku-2024)（デジタルツイン実現プロジェクト） | LAS（16点/m²以上）、グリッド 0.5m（参考 0.25m）、JGD2011 IX系 | ◎ | CC BY 4.0 | 昭島市、福生市 |
| 静岡県 | [VIRTUAL SHIZUOKA 中・西部](https://www.geospatial.jp/ckan/dataset/virtual-shizuoka-mw) ほか | LAS（LP＋MMS）、グラウンドデータ、グリッドデータ、JGD2011 VIII系 | ◎ | CC BY 4.0 / ODbL | 焼津市 |
| 山梨県 | [山梨県点群データ（航空LP・MMS）](https://www.geospatial.jp/ckan/dataset/yamanashi-pointcloud-2024) | LAS、県全域、JGD2011 VIII系 | ◎ | CC BY 4.0 / ODbL | 甲府市 |
| 神奈川県 | [令和3年度 横浜南部・湘南・横須賀三浦](https://www.geospatial.jp/ckan/dataset/kanagawa-2021-pointcloud) ほか（R1〜R6） | 点群 | ◎ | CC BY 4.0 | 横須賀市、平塚市、綾瀬市 |
| 兵庫県 | [全域 DEM](https://www.geospatial.jp/ckan/dataset/2010-2018-hyogo-geo-dem)、[全域 DSM](https://www.geospatial.jp/ckan/dataset/2010-2018-hyogo-geo-dsm)（2010〜2018年度） | 1m、XYZ テキスト、JGD2011 V系 | ◎ | CC BY 4.0（ページ内の表示） | 尼崎市、たつの市、上郡町 |
| 兵庫県 | [50cm DEM](https://www.geospatial.jp/ckan/dataset/2022-hyougo-geo-dem)・[DSM](https://www.geospatial.jp/ckan/dataset/2022-hyougo-geo-dsm)（2021〜2022年度）、[Terrain-RGB タイル](https://www.geospatial.jp/ckan/dataset/dem05_hyogo) | 0.5m | × 森林が中心（尼崎・たつの・神戸の市街地のタイルは空） | CC BY 4.0 | ― |
| 鳥取県 | [数値標高モデル(DEM)0.5m](https://www.geospatial.jp/ckan/dataset/dem05_tottori) | 0.5m GeoTIFF、Terrain-RGB・PNG 標高タイル | ◎（鳥取駅周辺にデータあり） | 政府標準利用規約 | 鳥取市 |
| 富山県 | [数値標高モデル（DEM）](https://www.geospatial.jp/ckan/dataset/dem) | 0.5m GeoTIFF | 【未確認】（森林部局の整備） | CC BY 4.0 | 富山市、魚津市 |
| 京都府 | [数値標高モデル（DEM）](https://www.geospatial.jp/ckan/dataset/dem05_kyoto) | 0.5m GeoTIFF | 【未確認】（森林部局の整備） | 独自利用規約 | 綾部市、大山崎町 |
| 愛媛県 | [数値標高モデル(DEM)0.5m](https://www.geospatial.jp/ckan/dataset/dem05_ehime) | 0.5m GeoTIFF（林野庁の計測を基に作成） | 【未確認】（森林中心の可能性が高い） | CC BY 4.0 | 大洲市 |
| 埼玉県 | [河川点群](https://www.geospatial.jp/ckan/dataset/river-pointcloud-saitama)、[道路点群](https://www.geospatial.jp/ckan/dataset/road-pointcloud-saitama) | UAV・MMS | △ 河川・道路の沿線だけ | CC BY 4.0 | 川越市、鴻巣市、新座市 |
| 島根県 | [河川 DEM 1.0m](https://www.geospatial.jp/ckan/dataset/shimane-kasen-dem) | 1m、河川の左右岸 20m | × 河川沿いだけ | PDL 1.0（国土地理院の承認を得た成果を使用） | 益田市 |
| 大阪府 | [グラウンドデータ](https://www.geospatial.jp/ckan/dataset/270008_grounddata) | 0.5m 相当 | × 森林だけ | CC BY 4.0 | 堺市 |
| 高知県・栃木県 | 0.5m DEM（[高知](https://www.geospatial.jp/ckan/dataset/dem05_kochi)、[栃木](https://www.geospatial.jp/ckan/dataset/dem05_tochigi)） | 0.5m、Terrain-RGB | 【未確認】 | CC BY 4.0 | （掲載市町村なし） |

**傾向**

- 市街地まで覆う高解像度データは、「デジタルツイン」「VIRTUAL SHIZUOKA」のような**県全域の点群整備**に多い（東京・静岡・山梨・神奈川）。
- 林業部局が整備した 0.5m DEM は森林が中心で、市街地を含まないことがある（兵庫・大阪）。鳥取のように市街地を含む例もあるので、個別に確かめる。

## 3. 検証対象の自治体選びへの影響

内水浸水想定区域・地形分類の詳細版・浸水実績の3つに加え、「市街地を覆う高解像度の標高」を条件にすると、
次の自治体が有力な候補になる（地形分類の詳細版と浸水実績の有無は未確認）。

- **東京都** 昭島市・福生市（0.5m / 0.25m グリッドがそのまま使える）
- **静岡県** 焼津市
- **山梨県** 甲府市（盆地の中小都市。地形で説明しやすいと予想される）
- **神奈川県** 平塚市・綾瀬市・横須賀市
- **兵庫県** 尼崎市・たつの市・上郡町（1m DEM・DSM。尼崎はゼロメートル地帯、上郡町は全域）
- **鳥取県** 鳥取市

国内の研究では、大都市ほど地形で内水を説明しにくいとされている（[手法選定](method-survey.md) §4）。
中小都市（甲府・焼津・たつの・上郡・鳥取・昭島・福生）と大都市寄り（尼崎・横須賀）を両方含められる。

## 4. 手法への影響

- **データ量**
  - 0.5m は 1km² あたり 400万セル、0.25m は 1,600万セルになる。市域 50km² なら 0.5m で約2億セル（float32 で約 0.8GB）。
  - 窪地の計算はタイルに分けて行い、流域の境界をまたぐ処理に注意する。
- **複数の解像度で比べる**
  - マニュアルは、25m より細かいメッシュでは微地形の影響が大きく出ると注意している。
  - 0.5m で細かい窪地を出しつつ、1m・5m・25m に集約した結果と比べ、解像度が一致度に与える影響を報告する。
  - 機械学習の特徴量は、自治体間でそろえるために共通の解像度（例: 1m）に揃えてから作る。
- **点群から DEM を作る場合**
  - LAS の地表点（クラス2）を 0.5m にグリッド化する（PDAL など）。
  - 県によって分類の品質や点密度が違う。静岡は「16点/m² 未満の場合がある」と注記している。
- **DSM と建物**
  - DSM − DEM が一定以上で、建物らしい形のセルを建物とし、嵩上げした場合としない場合を比べる。
  - PLATEAU の建物モデルがある自治体では、それとも突き合わせる。
- **計測時期のずれ**
  - 標高の計測年度（2010〜2025年度）と、内水浸水想定区域の作成時期・浸水実績の年代がずれる。
  - 造成された場所は、差分として注記する。
- **座標系**
  - 県ごとに平面直角座標系の系が違う（東京 IX系、静岡・山梨 VIII系、兵庫 V系など）。
  - 自治体ごとにその系で計算し、保存は EPSG:6668 に揃える（[調査メモ](naisui-research-notes.md) §4）。

## 5. 未確認事項

- 富山・京都・愛媛の 0.5m DEM が市街地を覆っているか（データ範囲図の PDF で確認する）
- 神奈川の点群にグリッド（DEM）が含まれるか、LAS だけか
- 各データの利用規約で、測量に用いる場合と、解析・可視化に用いる場合の扱いの違い
- 大阪府・愛知県など、G空間情報センター以外の県独自ポータルで公開されている標高データ（例: 広島県 DoboX）
