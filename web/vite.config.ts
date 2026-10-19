import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 后端默认 http://127.0.0.1:8000（见 server/README.md）。开发时走代理，前端只用相对路径 /api。
const backend = process.env.LABINFER_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": backend },
    // 设计素材（design/assets）在仓库根目录，直接引用，不复制进 web/
    fs: { allow: [".."] },
  },
});
