import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  base: '/shape/',
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        article: resolve(__dirname, 'article.html'),
        demo: resolve(__dirname, 'demo.html'),
        'budget-demo': resolve(__dirname, 'budget-demo.html'),
      },
    },
  },
})
