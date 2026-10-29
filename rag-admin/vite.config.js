import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // 管理台对外部署在 /admin/ 子路径下：
  //   80 端口统一入口 -> /        员工聊天页
  //                     /admin/   管理台（本应用）
  // 若改回根路径部署，需同步修改 rag-admin/nginx.conf 中的 location。
  base: '/admin/',
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true
      }
    }
  }
})