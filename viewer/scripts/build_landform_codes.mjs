// -----------------------------------------
// 地形分類のコード表（src/landform-codes.json）を地理院の style.js から作る。
//
//   node scripts/build_landform_codes.mjs
//
// 地形分類の GeoJSON タイルは属性が `code` だけで、分類名・色・成り立ち・リスクは
// 地理院が配っている Leaflet 用の style.js（関数の中の配列）にしか無い。
// 自然地形・人工地形で同じ style.js を配っているので 1 本から作る。
// style.js は eval が要る形式なので、ビューワの実行時には読まず、ここで JSON に焼く。
// -----------------------------------------
import { writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)))
const URL_STYLE =
  'https://cyberjapandata.gsi.go.jp/xyz/experimental_landformclassification1/style.js'

/**
 * 内水に関係が深い分類（調査メモ §3.2）。分類名で指定する。
 * 盛土地・埋立地は「盛土で窪地が消えていても元の地形がリスクを持つ」ので含める。
 */
const NAISUI = new Set([
  '凹地・浅い谷',
  '後背低地･湿地',
  '旧河道',
  '落堀',
  '旧水部',
  '干拓地',
  '盛土地･埋立地',
])

const src = await (await fetch(URL_STYLE)).text()
const style = eval(`(${src})`)
const arrayIn = (fn) =>
  eval(`[${fn.toString().match(/new Array\(([\s\S]*?)\);/)[1].replace(/\/\/.*$/gm, '')}]`)

const colors = new Map(arrayIn(style.geojsonOptions.style).map(([c, col]) => [String(c), col]))
const rows = arrayIn(style.geojsonOptions.onEachFeature)

// 分類名ごとにまとめる。コードは資料ごと（土地条件図・治水地形分類図…）に別番号が
// 振られているが、分類名・色・説明は同じ。
const classes = new Map()
for (const [code, name, origin, risk] of rows) {
  const c = String(code)
  // 99xx は「拡大すると表示されます」の範囲ポリゴン、100〜106 は資料の範囲。
  // 1〜71 は広域版（z13 以下）の分類。z14 以上しか読まないので落とす。
  if (Number(c) < 10000 || c === '999999') continue
  if (!classes.has(name)) {
    classes.set(name, { name, color: colors.get(c) ?? '#ffffff', naisui: NAISUI.has(name), origin, risk, codes: [] })
  }
  classes.get(name).codes.push(c)
}

// 人工地形のコード（110xx・401xxxx）かどうか。凡例を自然地形と人工地形に分けるのに使う。
const isArtificial = (code) => /^110\d\d$/.test(code) || /^40\d{5}$/.test(code)
const out = [...classes.values()].map((c) => ({ ...c, artificial: c.codes.every(isArtificial) }))

const missing = [...NAISUI].filter((n) => !classes.has(n))
if (missing.length) throw new Error(`内水関連の分類名が style.js に無い: ${missing.join(', ')}`)

await writeFile(
  join(ROOT, 'src', 'landform-codes.json'),
  JSON.stringify({ source: URL_STYLE, generated: new Date().toISOString().slice(0, 10), classes: out }, null, 1) + '\n',
)
console.log(`${out.length} 分類 / ${out.reduce((n, c) => n + c.codes.length, 0)} コード`)
for (const c of out) console.log(`${c.artificial ? '人工' : '自然'} ${c.naisui ? '内水' : '    '} ${c.color} ${c.name} (${c.codes.join(',')})`)
