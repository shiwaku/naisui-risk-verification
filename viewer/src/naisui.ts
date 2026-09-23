import type { LayerSpecification, RasterSourceSpecification } from 'maplibre-gl'

// ---- 内水（雨水出水）浸水想定区域（重ねるハザードマップ） ----
//
// 検証の「正解データ」。地形から推定した内水の起こりやすい場所と見比べるために重ねる。
// 重ねるハザードマップのオープンデータ配信（統合版）をラスタタイルのまま使う。
//   https://disaportal.gsi.go.jp/hazardmapportal/hazardmap/copyright/opendata.html#naisui
//
// - 掲載はオープンデータ化を許可した市町村だけ（2026-09 時点で 65 市町村）。
//   国土数値情報 A51 とは収録範囲が違う
// - 浸水深 0〜0.1m の範囲は表示されない（重ねるハザードマップの統一基準）
// - 河川の氾濫・高潮による浸水は考慮していない（内水だけの想定）

export const NAISUI_SOURCE = 'naisui'
export const NAISUI_ID = 'naisui'

const NAISUI_TILES = 'https://disaportaldata.gsi.go.jp/raster/02_naisui_data/{z}/{x}/{y}.png'

/** 配信されるズーム（オープンデータ一覧の記載）。これより深いズームは拡大表示する。 */
const NAISUI_MINZOOM = 2
const NAISUI_MAXZOOM = 17

/** 市町村ごとの掲載状況（全域か一部地域か）。パネルから案内する。 */
export const NAISUI_LIST_URL = 'https://disaportal.gsi.go.jp/hazardmapportal/hazardmap/copyright/naisui.html'

const NAISUI_ATTRIBUTION =
  '<a href="https://disaportal.gsi.go.jp/hazardmapportal/hazardmap/copyright/opendata.html#naisui" target="_blank" rel="noopener">「ハザードマップポータルサイト」</a>（内水浸水想定区域）'

/**
 * 既定の不透明度。浸水実績（0.35）を上に重ねても浸水深の段が読める濃さ。
 * 配信タイルの色は淡く、下に敷く地形分類の色と混ざりやすいので半透明より少し濃くする。
 */
export const DEFAULT_NAISUI_OPACITY = 0.75

export function naisuiSourceSpec(): RasterSourceSpecification {
  return {
    type: 'raster',
    tiles: [NAISUI_TILES],
    tileSize: 256,
    minzoom: NAISUI_MINZOOM,
    maxzoom: NAISUI_MAXZOOM,
    attribution: NAISUI_ATTRIBUTION,
  }
}

export function naisuiLayer(opacity: number): LayerSpecification {
  return {
    id: NAISUI_ID,
    type: 'raster',
    source: NAISUI_SOURCE,
    paint: {
      'raster-opacity': opacity,
      // 補間すると段の境界に中間色が出て、凡例にない色になる
      'raster-resampling': 'nearest',
    },
  } as LayerSpecification
}

/**
 * 凡例。色は配信元の凡例画像（img/naisui_legend.png）から読み取った値。
 * 市町村によっては旧凡例（0.1〜0.3m / 0.5〜1m の区分）で作られているため、それも並べる。
 */
export const NAISUI_LEGEND: { color: string; label: string; old?: boolean }[] = [
  { color: '#f7f5a9', label: '0.1〜0.5m' },
  { color: '#ffd8c0', label: '0.5〜3m' },
  { color: '#ffb7b7', label: '3〜5m' },
  { color: '#ff9191', label: '5〜10m' },
  { color: '#f285c9', label: '10〜20m' },
  { color: '#dc7adc', label: '20m〜' },
  { color: '#ffffb3', label: '0.1〜0.3m', old: true },
  { color: '#f8e1a6', label: '0.5〜1m', old: true },
]
