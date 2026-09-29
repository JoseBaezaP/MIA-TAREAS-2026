import preact from '@preact/preset-vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [preact()],
  server: {
    // En desarrollo (`npm run dev`, puerto 5173) las llamadas a /api van a FastAPI (8000).
    // Así el navegador ve un solo origen, igual que en producción, y la cookie funciona.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  // `npm run build` genera archivos estáticos en dist/, que sirve FastAPI (un solo servidor).
  build: { outDir: 'dist' },
})
