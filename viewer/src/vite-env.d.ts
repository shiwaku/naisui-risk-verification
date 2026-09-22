/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 浸水実績 PMTiles の配信先を差し替える（既定は GitHub Pages 上の変換結果）。 */
  readonly VITE_PMTILES_URL?: string
}

/** vite.config.ts の define で埋め込むビルド時刻。 */
declare const __BUILD_TIME__: string

/**
 * vt-pbf は型を同梱していない。@types/vt-pbf は古い geojson-vt の型に依存していて
 * 同梱型を持つ geojson-vt 5 と食い違うため、使う関数だけ宣言する。
 */
declare module 'vt-pbf' {
  import type { LegacyTile } from 'geojson-vt'
  export function fromGeojsonVt(
    layers: Record<string, LegacyTile>,
    options?: { version?: number; extent?: number },
  ): Uint8Array
}
