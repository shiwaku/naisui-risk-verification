import { defineConfig } from 'vite'

export default defineConfig(({ command }) => ({
  // 配信先（リポジトリ名・Pages の構成）が未定なので相対パスで出す。
  // どのパスに置いても public/ の JSON と assets を同じ階層から引ける。
  base: command === 'build' ? './' : '/',
  build: {
    outDir: '../app',
    emptyOutDir: true,
    // maplibre-contour / pmtiles が最上位 await を含むため ES2022 が必要
    target: 'es2022',
  },
  server: {
    port: 5175,
    strictPort: true,
    // Windows 上のファイルを WSL 側から見る構成ではファイル変更イベントが
    // 届かず、dev サーバが古い変換結果を返し続ける。ポーリングで検知する。
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
  define: {
    __BUILD_TIME__: JSON.stringify(
      new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC',
    ),
  },
}))
