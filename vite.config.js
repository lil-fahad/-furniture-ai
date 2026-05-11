import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  root: 'frontend',
  build: {
    outDir: 'dist'
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./frontend/src/setupTests.js'],
    include: ['frontend/src/**/*.{test,spec}.{js,jsx}'],
    root: '.',
  },
})
