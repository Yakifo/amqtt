import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import svgr from 'vite-plugin-svgr';

export default ({mode}: {mode: string}) => {
  console.log(`mode: ${mode}`);
// https://vite.dev/config/
  return defineConfig({
    plugins: [
      react(),
      svgr(),
    ],
  });
}
