import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// https://vitejs.dev/config/
export default defineConfig({
  base: '/infrasecurity/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/clientsecurity': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/infrasecurity/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/infrasecurity/clientsecurity': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
