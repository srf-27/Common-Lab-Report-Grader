# HeroUI 全站 SPA：接入、路由、组件与 HIG 取值

> **状态：旧版存档。** HeroUI / Tailwind / framer-motion 已从依赖中移除，当前前端为纯 CSS 令牌 + 自写组件；本文仅保留作迁移记录。

> 2026-10-21 更新：Jinja 经典版已整体删除，本文涉及 `/classic`、`templates/`、mammoth 的内容仅作历史记录。


现状：**前端已整站迁移为 React SPA**（React 19 + HeroUI 2.8 + Tailwind 3.4 + Vite 6），Flask 仅提供 JSON API 与文件下载；Jinja 版页面保留在 `/classic` 及原有路径，作为回退。

```
浏览器 ── /app/*  ──> React SPA（客户端路由）
             │
             └── fetch /api/* 与既有表单端点 ──> Flask（state / 评分线程 / 文件）
```

- `/` 在构建产物存在时返回 SPA，否则重定向到 `/classic`（经典版）。
- `/app/<任意子路径>` 返回同一份 `index.html`，由客户端路由解析。
- 经典版仍在 `/classic`、`/rubric_review`、`/reports_list` 等原路径可访问。

---

## 1. 构建与运行

```bash
cd frontend
npm install --registry=https://registry.npmmirror.com   # 默认源在部分网络下会卡住
npm run build          # 产物写入 src/experiment_report_grader/static/ui/
python run.py          # 打开 http://127.0.0.1:5000/
```

- `vite.config.js`：`base: "/static/ui/"`，`outDir` 指向 Flask 的 `static/ui`，开发模式代理 `/api`、`/static` 与全部表单端点。
- `static/ui/` 已在 `.gitignore` 中，部署时执行 `npm ci && npm run build`；未构建时根路径自动回退经典版。
- 构建体积：JS 943 KB（gzip 268 KB）、CSS 246 KB（gzip 29 KB）。后续可按页 `import()` 拆包。

---

## 2. 路由与接口

| SPA 路径 | 页面 | 取数接口 | 写操作（沿用表单端点） |
|---|---|---|---|
| `/app` | 工作台：三步卡片、指标、任务进度、一致性 | `GET /api/bootstrap`、`GET /task_status` | `POST /upload_criteria`、`/process_criteria`、`/upload_reports`、`/process_reports`、`/task_cancel` |
| `/app/rubric` | 评分细则：维度卡片、五级判据、补全、校验 | `GET /api/rubric` | `POST /rubric_table_save`、`/rubric_gen_cell`、`/calibrate_upload` |
| `/app/calibrate` | 校准打分与对比 | `GET /api/calibration` | `POST /api/calibration/submit` |
| `/app/reports` | 报告列表、筛选、原文阅读器 | `GET /api/reports` | — |
| `/app/report/:name` | 维度详情、学生信息、图片 | `GET /api/report/<name>` | `POST /update_student/<name>` |
| `/app/select` | 选择要评分的报告 | `GET /api/select` | `POST /start_grading` |
| `/app/progress` | 评分进度与取消 | `GET /grading_status` | `POST /grading_cancel` |
| `/app/results` | 结果、改等级、终审、重评、一致性 | `GET /api/results` | `POST /update_scores`、`/approve_report/<id>`、`/regrade/<id>` |
| `/app/roster` | 花名册编辑、可疑/缺交 | `GET /api/roster` | `POST /roster/upload`、`/roster/save` |
| `/app/settings` | 协议切换、OCR、向量库 | `GET /api/settings` | `POST /settings`、`/settings/ocr_check` |
| `/app/mcp` | 插件挂载、测试、参考文本 | `GET /api/mcp`、`/mcp/test/<name>` | `POST /mcp/add`、`/mcp/remove`、`/mcp/mount`、`/mcp/refresh` |

写操作采用「表单编码 POST → 重新拉取 JSON」：不复制业务逻辑，评分线程、导出、RAG 入库仍只有一份实现。

---

## 3. 组件与场景

| HeroUI 组件 | 场景 |
|---|---|
| `Card` / `CardBody` | 分组容器（工作台步骤、设置分组、维度块） |
| `Button` | 主操作 `color="primary"`；次级 `variant="bordered"`；文字操作 `variant="light"`；危险操作 `color="danger" variant="light"` |
| `Chip` | 阶段、状态、总分、相似度；全部带圆点或文字，不只靠颜色 |
| `Accordion` / `AccordionItem` | 评分结果逐份展开；一致性分析 |
| `Input` / `Select` / `Textarea` | 全部 `variant="bordered"`（白底 + 发丝线，贴合 iOS 文本栏） |
| `Switch` | 机械判决、SSL |
| `Checkbox` / `RadioGroup` | 选择报告、校准 A–E |
| `Progress` | 生成细则 / 提取报告进度（`aria-label`） |
| `Dropdown` | 课程切换、移动端「更多」 |
| `Spinner` | 首屏与异步占位 |
| `Modal` | 细则校验告警的二次确认 |

自建部分仅有布局（Tailwind 工具类）与三个基础模块：`components/ui.jsx`（页头、字段、空态、状态徽章）、`components/content.jsx`（Markdown 块、原文抽屉）、`lib/*`（路由、请求、Markdown）。

---

## 4. Apple HIG 取值

| 维度 | 取值 |
|---|---|
| 字体 | 系统栈（Apple 设备即 SF Pro），1rem = 17px；阶梯 34/28/22/20/17/16/15/13/12/11；最小 11 点，不用细体 |
| 间距 | 8pt 栅格；页面边距 16（紧凑）/ 32–40（常规）；分组内 12–16 |
| 配色 | 语义令牌：background `#f2f2f7`/`#000`、content1 `#fff`/`#1c1c1e`、label 黑白；填充按钮 `#0066cc`（白字 5.6:1）；深色 `#0a84ff`（黑字 5.8:1） |
| 圆角 | 分组 10（HeroUI `radius.small/medium/large` = 10/12/14）、输入 10、胶囊按钮 |
| 动效 | 200–320ms，`cubic-bezier(0.32,0.72,0,1)`；`prefers-reduced-motion` 全关；按钮有按压态 |
| 层级 | 常规：左侧边栏（评阅/设置两组）；紧凑（<768）：底部标签栏 5 项；每屏一个主按钮 |
| 无障碍 | 点击区 ≥44（列表项 `min-h-11`）；可见焦点环；`aria-current` / `aria-pressed` / `aria-live`；表格有 `aria-label`；图标按钮有 `aria-label`；表单错误用 `isInvalid` + 文案 |

字体与 SF Symbols 为 Apple 授权素材（macOS 安装包），不随仓库分发；图标按 SF Symbols 的 24 网格与 1.6 描边绘制。

---

## 5. 交互与兜底

- **上传**：选择文件即上传，成功后才点亮「生成 / 提取」；有任务时按钮禁用。
- **进度**：`/task_status` 与 `/grading_status` 轮询，完成后自动刷新数据；离开页面任务继续。
- **空/缺数据**：无细则、无报告、无结果时按钮禁用并给出下一步入口；终审在评分进行中或细则变更后禁用。
- **错误**：接口错误在页面顶部以 `Note tone="danger"` 显示，不弹原生 alert。
- **原文阅读器**：PDF 用 iframe，DOCX 走 mammoth，文本按分页渲染 Markdown 并做 KaTeX 排版；Esc/遮罩关闭。
- **移动端**：底部标签栏 + 「更多」弹层；表格横向滚动且操作列吸附。
- **长列表主操作常驻**：「选择要评分的报告」把「开始评分（已选 N 份）」放在 `sticky bottom`（移动端抬高 49px 让开标签栏），20 份报告滚到底也不用回顶部。
- **折叠面板**：指示器为右向箭头，展开转 90° 变下箭头（`disclosure` 于 `components/ui.jsx`），与 Apple 展开三角方向一致。

---

## 6. 接入踩坑（已解决，供复现参考）

| 现象 | 原因 | 处理 |
|---|---|---|
| `npm install` 长时间无产物 | 默认 registry 不可达 | `--registry=https://registry.npmmirror.com` |
| 组件几乎无样式（CSS 仅 23 KB） | `@heroui/theme` 嵌套在 `@heroui/react/node_modules` 下，Tailwind content 未匹配 | content 增加嵌套通配；CSS 增至 246 KB |
| 主题色不生效 | `themes.light` 需要 `{ colors: {...} }` | 包一层 `colors` |
| 大标题只有 19px | `text-large` 与 HeroUI 内置字号冲突 | 自定义阶梯改名 `text-display` |
| 深色模式不生效 | 深色变量挂在 `.dark` | `darkMode: "class"` + `matchMedia` |
| 页面空白 `Cannot access 'X' before initialization` | 导航表引用图标 const（TDZ）/ 页面与 App 循环 import | 导航表后置；上下文拆到 `lib/app-context.js` |
| 侧栏选中项多一个对勾 | Listbox 默认 `selectedIcon` | `itemClasses={{ selectedIcon: "hidden" }}` |
| 次级文字 3.2:1 | HeroUI `default-500` 是 `#8e8e93` | 改为 `#6c6c70`（深色 `#aeaeb2`）；语义色 500–700 压深 |
| 判据文本框出现内部滚动条 | Textarea 默认 `maxRows` | `minRows={4} maxRows={30}` |
| 折叠箭头收起时是「‹」 | HeroUI 默认左向箭头，展开时容器逆时针转 90° | 换成右向箭头，展开时再叠加 `rotate-180`：`› → ⌄` |
| 浏览器请求 `/favicon.ico` 报 404 | 页面未声明图标 | `static/favicon.svg` + 两版 head 声明 + `/favicon.ico` 路由 |

---

## 7. 验收结果

- **测试**：`python tests/run_all.py` → **51 passed, 0 failed**（连续 5 轮），含 `/app` 外壳与 7 个页面接口的结构断言。
- **对比度**：浅色/深色 × 8 个 SPA 页面 → **0 处**低于 WCAG AA（正文 4.5:1）。
- **响应式**：390 / 1440 宽度无页面级横向滚动；768 以下切底部标签栏。
- **控制台**：10 个 SPA 路由 0 个 JS 错误（含滚动、筛选、嵌套导航、阅读器）。
- **交互抽测**：侧栏跳转不刷新、筛选 `aria-pressed` 生效、原文抽屉分页与 KaTeX、结果页折叠列表、花名册增删行列。

## 8. 已知限制

- 单包 943 KB JS：HeroUI + framer-motion 占主要体积，后续按页 `import()` 或 `manualChunks` 拆包。
- KaTeX 脚本为非 ES module，构建期有两条「can't be bundled」警告，运行时从 `/static/vendor` 正常加载。
- 经典版与 SPA 并行存在，样式令牌同源但组件实现不同；迁移稳定后可删除 `templates/` 与 `style.css`。
- 服务端仍是单进程内存状态，SPA 不改变并发模型。
