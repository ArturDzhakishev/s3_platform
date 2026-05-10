import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Адрес бэкенда — меняй под свою среду:
//   localhost:8000  → разработка
//   http://192.168.1.x:8000 → продакшен-сервер
const BACKEND_URL = process.env.VITE_BACKEND_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: BACKEND_URL,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
