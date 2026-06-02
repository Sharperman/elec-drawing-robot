import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import electron from 'vite-plugin-electron';
import renderer from 'vite-plugin-electron-renderer';
import path from 'path';

export default defineConfig({
  plugins: [
    react(),
    electron([
      {
        entry: 'electron/main.ts',
        // 纯前端开发时不启动 Electron，仅构建主进程代码
        onstart() {
          // skip auto-start in dev
        },
        vite: {
          build: {
            outDir: '../dist-electron',
            rollupOptions: {
              external: ['electron', 'electron-log', 'child_process', 'path', 'url'],
            },
          },
        },
      },
      {
        entry: 'electron/preload.ts',
        onstart() {
          // skip auto-start in dev
        },
        vite: {
          build: {
            outDir: '../dist-electron',
            rollupOptions: {
              external: ['electron'],
            },
          },
        },
      },
    ]),
    renderer(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
