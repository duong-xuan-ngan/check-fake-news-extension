import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Options page build (account / sign-in UI). Loaded via chrome-extension://, so
// it can be a normal ES module app with its own HTML entry.
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  envDir: mode === 'production' ? '../production' : '..',
  build: {
    outDir: '../extension',
    emptyOutDir: false,
    rollupOptions: {
      input: 'options.html',
      output: {
        entryFileNames: 'options.js',
        chunkFileNames: 'options-[hash].js',
        assetFileNames: 'options.[ext]',
      },
    },
  },
}))
