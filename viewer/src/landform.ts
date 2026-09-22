import type { LayerSpecification, VectorSourceSpecification } from 'maplibre-gl'
import GeoJSONVT from 'geojson-vt'
import { fromGeojsonVt } from 'vt-pbf'
import codes from './landform-codes.json'

// ---- 地形分類（国土地理院 ベクトルタイル提供実験） ----
//
// 配信は GeoJSON タイルで、MapLibre はこれをタイルとして読めない（GeoJSON ソースは
// 1ファイル丸ごとしか扱えない）。`landform://` プロトコルでタイルを取得し、
// その場で MVT に詰め替えて vector ソースとして渡す。
//
// 地理院から取得するのは z14 のタイルだけにする。
//   - 人工地形は z4〜13 が「おおよその範囲図」で実データではない
//   - 自然地形の z13 以下は広域版（山地・台地・低地など）で、凹地・旧河道・後背低地
//     といった内水に効く分類が無い
//   - z14 と z16 の形状は同じ（実測: 1枚の z14 と、その子 z16 16枚の頂点数の差は
//     タイル境界で切れた分の約 7%）。z15 以上は z14 を拡大表示すれば足りる
//
// z13 では、子にあたる z14 の4枚を取得してまとめ、z13 のタイルとして返す。
// これで z13 の広さでも詳細版の分類が見える。z12 まで広げると画面1枚で
// z14 を約190枚（種別ごと）取ることになり、地理院のサーバにも重いので z13 で止める。

export const LANDFORM_PROTOCOL = 'landform'
/** 地理院から取得するズーム（詳細版）。 */
const DATA_ZOOM = 14
/** 表示を始めるズーム。これ未満では地形分類を出さない。 */
export const LANDFORM_MINZOOM = 13

const GSI_BASE = 'https://cyberjapandata.gsi.go.jp/xyz'

export type LandformKind = 'natural' | 'artificial'

const KIND_DIR: Record<LandformKind, string> = {
  natural: 'experimental_landformclassification1',
  artificial: 'experimental_landformclassification2',
}

export const LANDFORM_SOURCE: Record<LandformKind, string> = {
  natural: 'landform-natural',
  artificial: 'landform-artificial',
}

export const LANDFORM_FILL_ID: Record<LandformKind, string> = {
  natural: 'landform-natural-fill',
  artificial: 'landform-artificial-fill',
}

/** 詰め替えた MVT 内のレイヤー名。 */
const TILE_LAYER = 'landform'

const LANDFORM_ATTRIBUTION =
  '<a href="https://www.gsi.go.jp/bousaichiri/lfc_index.html" target="_blank" rel="noopener">地形分類（国土地理院 ベクトルタイル提供実験）</a>'

// ---- コード表 ----

export interface LandformClass {
  name: string
  color: string
  /** 内水に関係が深い分類か（調査メモ §3.2）。 */
  naisui: boolean
  /** 人工地形の分類か。凡例を分けるのに使う。 */
  artificial: boolean
  origin: string
  risk: string
  codes: string[]
}

/** scripts/build_landform_codes.mjs が地理院の style.js から作った表。 */
export const LANDFORM_CLASSES: LandformClass[] = (codes as { classes: LandformClass[] }).classes

const byCode = new Map<string, LandformClass>()
for (const c of LANDFORM_CLASSES) for (const code of c.codes) byCode.set(code, c)

export const landformByCode = (code: unknown): LandformClass | undefined => byCode.get(String(code))

// ---- プロトコル ----

/** MapLibre 名前空間のうち、ここで必要な部分だけ（terrain.ts と同じ理由で緩く受ける）。 */
interface MaplibreLike {
  addProtocol(name: string, fn: (...args: any[]) => any): void
}

/**
 * 詳細版（z14）の GeoJSON タイルを1枚取得する。データが無い区域は 404 が返るので空にする。
 * 取得に失敗した1枚のために z13 のタイル全体を落とさないよう、ネットワークエラーも空にする
 * （中断だけは呼び出し元へ伝える）。
 */
async function fetchDataTile(
  dir: string,
  x: number,
  y: number,
  signal: AbortSignal,
): Promise<GeoJSON.Feature[]> {
  try {
    const res = await fetch(`${GSI_BASE}/${dir}/${DATA_ZOOM}/${x}/${y}.geojson`, { signal })
    if (!res.ok) return []
    return ((await res.json()) as GeoJSON.FeatureCollection).features
  } catch (err) {
    if (signal.aborted) throw err
    return []
  }
}

/**
 * `landform://<kind>/{z}/{x}/{y}` を登録する。地図の生成前に一度だけ呼ぶ。
 *
 * 要求されたタイルに含まれる z14 のタイル（z14 なら1枚、z13 なら子の4枚）を取得し、
 * まとめて MVT に詰めて返す。z13 では子タイルの境界で地物が切れたまま並ぶが、
 * 輪郭を描かない塗りだけなので継ぎ目は見えない。
 *
 * 分類名と内水フラグはここで属性に焼き込む。スタイル側でコード 82 個の match を
 * 書くより、表を1か所（landform-codes.json）に置いたほうが凡例と食い違わない。
 */
export function registerLandformProtocol(maplibre: MaplibreLike): void {
  maplibre.addProtocol(
    LANDFORM_PROTOCOL,
    async (params: { url: string }, abortController: AbortController) => {
      const [kind, zs, xs, ys] = params.url.replace(`${LANDFORM_PROTOCOL}://`, '').split('/')
      const [z, x, y] = [Number(zs), Number(xs), Number(ys)]
      const dir = KIND_DIR[kind as LandformKind]

      const n = 2 ** (DATA_ZOOM - z)
      const children: Promise<GeoJSON.Feature[]>[] = []
      for (let dx = 0; dx < n; dx++) {
        for (let dy = 0; dy < n; dy++) {
          children.push(fetchDataTile(dir, x * n + dx, y * n + dy, abortController.signal))
        }
      }
      const features = (await Promise.all(children)).flat()
      if (!features.length) return { data: new Uint8Array() }

      for (const f of features) {
        const code = String(f.properties?.code ?? '')
        const cls = byCode.get(code)
        f.properties = { code, name: cls?.name ?? '', naisui: cls?.naisui ? 1 : 0, color: cls?.color ?? '#ffffff' }
      }
      // 要求されたタイルの範囲ぶんのデータなので、そのズームまで切れば目的のタイルが取れる。
      // tolerance 0 にするのは、窪地の縁を読むのに形を間引かないため。
      const index = new GeoJSONVT(
        { type: 'FeatureCollection', features },
        { maxZoom: z, indexMaxZoom: z, tolerance: 0 },
      )
      const tile = index.getTile(z, x, y)
      if (!tile) return { data: new Uint8Array() }
      return { data: fromGeojsonVt({ [TILE_LAYER]: tile }, { version: 2 }) }
    },
  )
}

export function landformSourceSpec(kind: LandformKind): VectorSourceSpecification {
  return {
    type: 'vector',
    tiles: [`${LANDFORM_PROTOCOL}://${kind}/{z}/{x}/{y}`],
    minzoom: LANDFORM_MINZOOM,
    maxzoom: DATA_ZOOM,
    attribution: LANDFORM_ATTRIBUTION,
  }
}

// ---- レイヤー ----

export type LandformMode = 'all' | 'naisui'

export const LANDFORM_MODES: { key: LandformMode; label: string }[] = [
  { key: 'naisui', label: '内水関連のみ' },
  { key: 'all', label: 'すべて' },
]

/** 地理院のスタイル（style.js）の既定の不透明度。 */
export const DEFAULT_LANDFORM_OPACITY = 0.5

export const landformFilter = (mode: LandformMode): unknown =>
  mode === 'naisui' ? ['==', ['get', 'naisui'], 1] : ['all']

/**
 * 塗り。色は地理院のスタイルに合わせる（地理院地図で見慣れた配色と対照できるように）。
 * 輪郭は付けない。隣り合う分類の境界は色の差で読めるうえ、浸水域の輪郭と紛れる。
 */
export function landformLayer(kind: LandformKind, mode: LandformMode, opacity: number): LayerSpecification {
  return {
    id: LANDFORM_FILL_ID[kind],
    type: 'fill',
    source: LANDFORM_SOURCE[kind],
    'source-layer': TILE_LAYER,
    minzoom: LANDFORM_MINZOOM,
    filter: landformFilter(mode) as never,
    paint: {
      'fill-color': ['get', 'color'] as never,
      'fill-opacity': opacity,
      'fill-antialias': false,
    },
  }
}

/** 凡例に並べる分類。表示モードと、表示している種別（自然・人工）で絞る。 */
export function landformLegend(mode: LandformMode, kinds: Record<LandformKind, boolean>): LandformClass[] {
  return LANDFORM_CLASSES.filter(
    (c) => (mode === 'all' || c.naisui) && (c.artificial ? kinds.artificial : kinds.natural),
  )
}
