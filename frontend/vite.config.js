import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 构建产物落到 Flask 的 static 目录，由 / 与 /app 路由加载
const TARGET = "http://127.0.0.1:5055";
const PROXIED = [
  "/api",
  "/static",
  "/session",
  "/task_status",
  "/task_cancel",
  "/grading_status",
  "/grading_cancel",
  "/upload_criteria",
  "/process_criteria",
  "/upload_reports",
  "/process_reports",
  "/rubric_gen_cell",
  "/rubric_table_save",
  "/calibrate_upload",
  "/start_grading",
  "/regrade",
  "/approve_report",
  "/update_student",
  "/update_scores",
  "/roster",
  "/settings",
  "/mcp",
  "/report_text",
  "/report_original",
  "/report_image",
  "/download",
];

export default defineConfig({
  base: "/static/ui/",
  plugins: [react()],
  build: {
    outDir: "../src/experiment_report_grader/static/ui",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5174,
    proxy: Object.fromEntries(PROXIED.map((path) => [path, TARGET])),
  },
});
