import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { vanillaExtractPlugin } from '@vanilla-extract/vite-plugin'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), vanillaExtractPlugin()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
target: 'http://localhost:7000',
        changeOrigin: true,
        secure: false,
        ws: true, // WebSocket支持
      },
'/health': {
        target: 'http://localhost:7000',
        changeOrigin: true,
      },
    },
  },
})
