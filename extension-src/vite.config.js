import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  envDir: mode === 'production' ? '../production' : '..',
  build: {
    outDir: '../extension',
    emptyOutDir: false,
    rollupOptions: {
      input: 'src/content.jsx',
      output: {
        entryFileNames: 'content.js',
        chunkFileNames: 'content-[hash].js',
        assetFileNames: 'content.[ext]',
      },
    },
  },
}))
