# 实验报告智能评阅系统（Common-Lab-Report-Grader）

> **初版，未完全审查，慎用。**

面向高校实验课的本地 Web 应用：教师上传评分标准与学生实验报告，系统按维度判级（A–E）、做内容安全与抄袭检测、支持教师逐份终审与成绩导出，并把终审报告沉淀为本课程的 RAG 案例库。可挂载 MCP 插件，用学科类 reference 辅助判决。

- 纯本地运行，数据只落 `data/output/sessions/<课程>/`
- 单个 Flask 进程，无数据库服务；前端构建一次后由 Flask 直接托管
- 全链路 LLM 调用都有兜底：模型失败不会静默给出分数，而是标记后交人工

---

## 1. 快速开始

```bash
# 1) 依赖（建议 Python 3.10+；项目内已有 .venv 时直接用）
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS / Linux

# 2) 配置：复制示例并填入模型信息（也可以启动后在「配置」页填）
cp config/config.example.yaml config/config.yaml

# 3) 前端（React + Vite，构建一次即可）
cd frontend && npm install --registry=https://registry.npmmirror.com && npm run build && cd ..

# 4) 启动
python run.py                       # http://127.0.0.1:5000  （SPA）
python run.py --port 8080 --host 0.0.0.0
```

模型只需 OpenAI 兼容接口（DeepSeek、通义、SiliconFlow、vLLM 等均可）：

```yaml
llm:
  backend: "openai"
  openai:
    api_key: "DEEPSEEK_API_KEY"        # 填环境变量名或明文 key
    base_url: "https://api.deepseek.com"
    model: "deepseek-chat"
    max_tokens: 16384
```

启动后从左到右走完工作台的 1→2→3 步即可，界面里的按钮会随数据是否齐备自动禁用/启用。

---

## 2. 使用流程

| 步骤 | 页面 | 做什么 | 结果落在 |
|---|---|---|---|
| ① 细则 | 工作台 / 评分细则 | 上传评分标准（.docx/.pdf/.txt）→ 生成结构化 Rubric → 按维度折叠编辑五级判据与权重 | `rubrics/rubric_current.json`、`rubric_latest.md` |
| ② 报告 | 工作台 / 报告管理 | 批量上传报告或压缩包 → 提取正文、图片、学生信息；同文重复自动去重 | `reports/<文件名>/text.md`、`images/`、`meta.json` |
| ③ 评分 | 选择评分报告 → 评分进行中 | 勾选本次要评的报告（同一学生只允许一份）→ 后台逐份评分 | `grading/grading_results.json` |
| ④ 终审 | 评分结果 | 逐份改等级、写评语、终审入库或打回重评 | `approved.json` + RAG 库 |
| ⑤ 导出 | 评分结果 / 报告管理 | 下载成绩 Excel、评分 JSON、被标记人员汇总 | `grading/grading_summary.xlsx` 等 |

辅助页面：

- **花名册**：上传 `.xlsx/.csv`，表头决定学生信息的提取与导出列；自动给出「缺交」「可疑（学号不在名册或姓名不一致）」。
- **插件**：登记并挂载 MCP 服务（见第 5 节）。
- **配置**：生成协议（OpenAI 兼容 / Ollama / 自定义 HTTP，切换后只显示该协议字段）、模型、OCR、向量库与嵌入，保存即生效；内置 OCR 自检。

### 界面规范（按 Apple HIG 重写）

前端是**从零重写的 React SPA**（`/` → `/app`），不依赖组件库与 CSS 框架，严格按 [Apple 人机界面指南](https://developer.apple.com/cn/design/human-interface-guidelines/) 的布局、导览、控件、排版、色彩与无障碍条款实现；设计令牌集中在 `frontend/src/styles.css`。

**排版**：系统字体优先（SF Pro / PingFang SC / Segoe UI Variable），字距随字号收紧（大标题 `-0.022em`，正文 `-0.004em`）。字号阶梯取自 iOS 动态字体表：大标题 31、标题 2 为 19、标题 3 为 17、正文 15、标注 13、脚注 12、说明 11.5——最小字号不低于 Guide 的 11 点。字号与间距用 `rem`，跟随用户的浏览器字号设置缩放。

**色彩**：语义色而非硬编码色。背景用 `systemGroupedBackground` 分层（`--bg` / `--surface` / `--fill`），前景用 `label` / `secondaryLabel` / `tertiaryLabel` / `separator`，强调色为系统蓝；浅色、深色各一套。文字对比度实测：正文 21:1、次要文字 4.74:1、强调色文字 5.57:1、等级色 5.2–5.4:1，均达 WCAG AA 4.5:1（深色模式下实心按钮为白字压蓝 3.65:1，与 iOS 原生一致，属已知例外）。

**布局与导览**：常规宽度是材质边栏（272px，毛玻璃 + 分组 + 选中高亮）+ 顶部工具栏；紧凑宽度（≤860px）边栏自动换成 5 项底部标签栏，其余入口收进「更多」sheet，深链如 `/app/report/<文件>` 仍可直接打开。内容区是 inset grouped 列表：分组标题在上、说明在下、行高 ≥52、分隔线从文字处内缩。工具栏标题在滚动出大标题后淡入，滚动前保持透明，内容从其下方穿过。

**控件**：按钮分 `filled / tinted / gray / plain / destructive` 五级，每屏只保留一个强调按钮；开关按 iOS 51×31、分段控制 2–5 段、等级用紧凑分段选择器。视觉尺寸 30–36px 的图标按钮用伪元素把命中区补到 44×44；触屏设备（`pointer: coarse`）下所有控件实际尺寸放大到 44，输入框字号提到 16px 以避免 iOS 聚焦缩放。

**动效**：页面切换 280ms 淡入 + 8px 上移（`cubic-bezier(.22,1,.36,1)`），折叠用 `grid-template-rows` 过渡，弹层移动端从底部整体升起、桌面端居中缩放，提示条底部堆叠且悬停暂停计时。全部动画只动 `transform` / `opacity`；`prefers-reduced-motion` 下退化为淡入淡出。

**无障碍**：跳转链接、`aria-current` / `aria-expanded` / `aria-pressed`、图标按钮 `aria-label`、对话框 `aria-modal` + Esc 关闭、可见焦点环；等级用「字母 + 颜色」双通道，不依赖颜色区分；支持 `prefers-contrast: more`（更实的文字与分隔线）与 `prefers-reduced-transparency: reduce`（材质变实色）。安全区用 `env(safe-area-inset-*)`，`-webkit-tap-highlight-color` 置空、`touch-action: manipulation`、`overscroll-behavior: none`，hover 样式全部包在 `(hover: hover) and (pointer: fine)` 里。

结构上分三层：

- `src/ui/`：按钮、分组列表、列表行、分段控制、开关、等级选择器、折叠块、sheet、提示条等基础件；
- `src/lib/`：请求封装、history 路由、数据钩子、状态上下文、Markdown/公式渲染；
- `src/pages/`：11 个页面，一页一文件。

路由用 History API，Flask 侧 `/app` 与 `/app/<path>` 都返回 `index.html`；Jinja 版仍保留在 `/classic` 作为回退。报告正文里的 `\( \)` / `\[ \]` 公式用本地 KaTeX 渲染。

### 页面交互约定

- 过长内容折叠：维度详情（每个维度一个可展开块）、评分结果（每份报告一张可展开卡片）、校准模式、学生信息、名册编辑、缺交/可疑名单、一致性分析、配置分组。
- 数据缺失时按钮不可交互：没有细则时「开始评分」禁用；没有上传文件时「生成/提取」禁用；没有评分结果时「下载 Excel」「终审」禁用；原始文件不在工作目录时「原文」禁用；细则改动后未重评的报告「终审」禁用并提示重评。
- 页面互跳：常规宽度用边栏、紧凑宽度用底部标签栏；工作台流程条 → 细则页/报告页/选择评分页；评分完成 → 逐份维度详情；报告行 → 维度详情，行内可直接改学生信息或打开原文。

---

## 3. 目录结构

```
run.py                     启动入口（--host/--port/--debug）
config/
  config.yaml              运行配置（含密钥，已在 .gitignore）
  config.example.yaml      配置模板
  mcp.yaml                 MCP 插件注册表（首次保存时自动生成）
src/experiment_report_grader/
  app.py                   所有 HTTP 路由（编排层，不含业务算法）
  factory.py               LLM 实例工厂（测试替换点）
  web/state.py             课程会话、目录、审批记录、MCP 挂载、状态补水
  web/tasks.py             后台任务进度（上传处理）
  nodes/                   评分业务
    grader.py              判级主流程、维度归一、RAG、相似度、导出
    rubric_generator.py    细则生成/单元格补全/偏差校验/校准对比
    rubric_io.py           权重归一、小计、校验收紧、Markdown
    verifier.py            机械判决：LLM 生成裁判代码 + 沙箱执行 + 规则回退
    agreement.py           一致性指标（κ / 加权 κ / α）
    report_extractor.py    报告解析调度（受保护文件）
  utils/
    llm_client.py          OpenAI/Ollama/自定义客户端（受保护文件）
    file_parser.py         PDF/DOCX/MD/压缩包解析（受保护文件）
    doc_reader.py          老式 .doc 解析（受保护文件）
    ocr_engine.py          OCR 后端（paddleocr / 视觉 API，受保护文件）
    ocr_check.py           OCR 自检（合成图 → 识别 → 相似度）
    injection_detector.py  提示注入检测（LLM 语义 + 不可见字符规范化）
    content_safety.py      内容安全检测（LLM 语义）
    privacy.py             隐私脱敏（LLM 实体替换 + 正则兜底）
  mcp/
    client.py              MCP 客户端（stdio / http JSON-RPC）+ 参考收集
    store.py               插件注册表读写与表单校验
  templates/               Jinja2 页面（15 个，/classic 回退）
  static/css/style.css     设计系统
docs/
  PROJECT_STRUCTURE.md     模块职责、数据流、扩展点
  HIG.md                   旧版界面规范（已被 SPA 取代，仅存档）
  HEROUI.md                旧版 HeroUI 接入说明（已被 SPA 取代，仅存档）
  MCP.md                   插件协议、示例、排障
  TESTING.md               测试矩阵与实测结果
frontend/                  React 19 + Vite 6 的 SPA（无组件库，构建到 static/ui）
  src/pages/               工作台、细则、校准、报告、详情、选卷、进度、结果、花名册、配置、插件
  src/ui/                  基础组件与图标
  src/lib/                 请求、路由、数据钩子、上下文、Markdown/公式
  src/styles.css           设计令牌与全部样式
tests/
  run_all.py               零依赖测试入口（无需 pytest）
  fake_llm.py              假模型：覆盖每条 LLM 分支
  unit/                    单元测试
  integration/             端到端点击流程 + 基准跑批脚本
  fixtures/                假 MCP 服务、cn_lab 基准材料
```

---

## 4. 配置说明（`config/config.yaml`）

| 键 | 说明 | 默认 |
|---|---|---|
| `llm.backend` | `openai` / `ollama` / `custom`（配置页可切换） | `openai` |
| `llm.ollama.base_url` / `model` | 本地 Ollama 地址与模型 | `http://localhost:11434` / — |
| `llm.custom.base_url` / `api_key` / `model` | 自定义 HTTP 网关 | — |
| `llm.openai.api_key` | 环境变量名或明文 key（程序会先查同名环境变量） | `DEEPSEEK_API_KEY` |
| `llm.openai.base_url` / `model` / `max_tokens` | 兼容接口地址、模型名、单次输出上限 | — |
| `ocr.backend` | `paddleocr`（本地）或 `api`（视觉大模型） | `paddleocr` |
| `ocr.paddleocr.language` | OCR 语言 | `ch` |
| `ocr.api.api_url/api_key/api_model` | 视觉 OCR 接口 | — |
| `grading.similarity_threshold` | 全文相似度告警线 | `0.92` |
| `grading.similarity_reject` | 判定为高度重复的线 | `0.97` |
| `grading.ocr_images` | 是否对报告插图跑 OCR（结果缓存到 `reports/*/.ocr/`） | `false` |
| `extraction.image_context_lines` | 图片上下文行数（保留项） | `2` |
| `vector_store.backend` | 向量库类型（当前 chroma） | `chroma` |
| `vector_store.chroma.mode` | `local`（每课程独立目录）或 `cloud`（Chroma Server） | `local` |
| `vector_store.embedding.backend` | `default`（内置离线）或 `openai`（`/embeddings`） | `default` |

> `config/config.yaml`、`config/config.example.yaml`、`embedding/*`、`utils/{llm_client,file_parser,doc_reader,ocr_engine}.py`、`nodes/report_extractor.py` 标注受保护（文件首行 `checked`）：改造时不修改；能力扩展走新模块。

---

## 5. MCP 插件（学科 reference 辅助判决）

### 5.1 登记插件

在「插件 → 添加插件」填表单，或直接写 `config/mcp.yaml`：

```yaml
servers:
  physics-ref:
    transport: stdio
    command: npx
    args: ["-y", "@your/physics-ref-server"]
    env:
      REF_API_KEY: "xxx"
    note: "物理实验学科参考"
  lab-http:
    transport: http
    url: "http://127.0.0.1:8931/mcp"
    headers: {}
```

- `stdio`：启动子进程，按行收发 JSON-RPC 2.0。
- `http`：POST JSON-RPC，兼容 `application/json` 与 `text/event-stream`（解析 `data:` 行），自动回传 `Mcp-Session-Id`。

### 5.2 挂载到课程

「插件 → 挂载到 <课程>」勾选服务器，并可选填：

| 字段 | 作用 |
|---|---|
| 资源过滤 | 每行一个 `fnmatch` 通配（如 `ref://physics/*`），留空读全部资源 |
| 检索工具名 | 调用该工具，参数 `{"query": "<维度名>"}`，取返回的 text 内容 |
| 学科提示词名 | 调用 `prompts/get`，把返回的 messages 作为学科指引 |
| 参考文本上限 | 注入提示词的总字符预算，默认 4000 |

挂载信息存在 `data/output/sessions/<课程>/mcp.json`，**按课程隔离**。

### 5.3 注入位置

评分开始前收集一次（不是每份报告一次），把文本填进评分提示词的「学科参考资料」段：

```
### 插件：physics-ref
【不确定度】不确定度：A 类按贝塞尔公式 s(x)/√n 计算……
```

失败兜底：插件不可用/超时/返回异常时，参考为空字符串，评分继续；「插件」页显示每台服务器的可用状态与错误原因。工具调用、提示词调用、资源读取各自有独立兜底，互不影响。

详见 [docs/MCP.md](docs/MCP.md)。

---

## 6. LLM 调用与兜底矩阵

| 环节 | 调用点 | 失败时的决策 |
|---|---|---|
| 提示注入检测 | `detect_injection` | 返回 `detection_failed`，该报告转人工审查，不评分 |
| 注入检测截断 | 文本 > 2 万字符 | 标记 `audit_truncated`，转人工，不静默放行 |
| 内容安全 | `check_content_safety` | fail-open 放行并记录 `detection_failed`（安全检测失败标记） |
| 隐私脱敏 | `anonymize_text` | 回退正则兜底（隐私是红线，必须替换） |
| 细则生成 | `RubricGenerator.generate_structured` | 无带 `doc_ref` 的维度 → 任务失败并提示；部分缺失 → 丢弃并记警告 |
| 单元格补全 | `generate_cells` | 返回非 JSON → 422 + 页面提示重试 |
| 偏差校验 | `validate_deviation` | 警告列表附「偏差校验 LLM 调用失败」 |
| 维度归类 | `Grader.assign_items` | 返回 `{}`，内容归入「未挂载内容」，评分继续 |
| 机械判决裁判 | `verifier.generate` / `run` | 生成失败或执行异常 → 回退 rubric 里的 `rules` 正则；仍不可判则交回 LLM |
| 报告评分 | `Grader.grade_single` | 无可解析分数 → 状态 `llm_failed`，不计入成绩，可一键重评（不伪造 C） |
| 学生信息提取 | `_extract_student` | 字段留空，人工在页面补 |
| 校准对比 | `RubricGenerator.calibrate` | 返回空 → 页面提示「模型未返回可解析的对比结果」 |
| MCP 工具/资源/提示词 | `mcp/client.collect` | 单台失败只写状态，参考为空，评分继续 |

不依赖 LLM 的确定性逻辑（权重归一、小计、相似度、导出、花名册匹配）不受上述影响。

---

## 7. 评分算法要点

- **维度与等级**：每个维度 A/B/C/D/E，E 只表示「未实现/缺失/整卷跑题/抄袭/白卷」，不是"比 D 更差"。等级分值与权重：`A=95, B=80, C=60, D=40, E=0`。
- **机械判决**：细则中可程序化判定的维度由 LLM 生成的 `verify(text)` 裁决（AST 白名单 + 受限 builtins，只允许 `re / math / json`）；生成或执行失败回退 `rules`（`exists` / `numeric_compare`）。
- **维度归一**：LLM 自创的简短维度名会被映射回细则名单，缺失维度记 C 并标注「请人工复核」，避免重复计分导致总分溢出。
- **防跑题**：提示词规则 + 细则生成时的强约束——与实验主题无关的内容不得高于 D。
- **RAG**：终审报告正文进全文库（相似度用），挂到维度的段落/图片进「维度库」（评分时作同维度历史参考）；示例报告按等级分值排序取前 1–2 份做 few-shot。
- **相似度**：全文向量最近邻，`≥0.92` 告警、`≥0.97` 标记高度重复；结果页可按「疑似抄袭」筛选。
- **一致性**：存在 `teacher_grades.json` 时，结果页展示 Cohen's κ、二次加权 κ、Krippendorff's α（按维度 + 总体 + 总分档位）。

---

## 8. 安全设计

1. **隔离会话**：每门课独立目录、独立向量库、独立挂载配置；切换课程即重建内存状态。
2. **上传即清洗**：文件名去路径与非法字符；压缩包按扩展名 + 文件头双判定；正文重复用规范化哈希去重。
3. **注入防护**：待审文本一律作为「数据」（JSON 字符串字面量 / `<REPORT>` 块）交给模型，不可见字符先规范化并附扫描摘要；命中即拦截。
4. **内容安全**：命中国家安全、暴恐、教唆犯罪等类别则 `blocked_safety`，不评分。
5. **隐私**：入 RAG 前用 LLM 替换姓名/学号/电话/邮箱/身份证/住址；LLM 不可用时正则兜底。
6. **路径安全**：下载接口做 `realpath` 前缀校验；原始文件只从本课程的 uploads/reports 目录取。
7. **导出可控**：未知状态一律 `N/A`，不会把失败报告算成 0 分。

---

## 9. OCR

- 默认只在 PDF 页面无文本（扫描页）时调用 OCR；报告插图默认用上下文文字，开启 `grading.ocr_images: true` 后对插图 OCR（结果缓存，二次评分不再重复识别）。
- 准确性自检（合成图 → 识别 → 与期望文本比对，忽略空白）：

```bash
python scripts/ocr_check.py            # 用配置文件里的 OCR 后端
python scripts/ocr_check.py --backend api
```

也可在「配置 → OCR → 运行 OCR 自检」点按钮查看结果。

实测（本机 paddleocr 3.7，中英混排 + 公式符号，阈值 0.85）：

| 期望 | 识别 | 相似度 |
|---|---|---|
| 实验报告 2023 逐差法 | 实验报告 2023 逐差法 | 1.000 |
| E=2.20e11 Pa | E=2.20e11 Pa | 1.000 |
| 不确定度 σ=0.35 mm | 不确定度σ=0.35 mm | 1.000 |
| — | **平均** | **1.000**（仅空格差异被忽略） |

结论：本地 OCR 对印刷体中文/数字/公式符号可用；手写体与低分辨率拍照扫描件仍需人工核对，页面会把该报告标为「扫描件」。

---

## 10. 测试

```bash
python tests/run_all.py          # 全部 51 项，无需 pytest
python tests/run_all.py -k mcp   # 按名字过滤
```

覆盖：

- 单元：权重归一/小计/校验收紧、机械判决与沙箱、注入检测解析与 fail-open、隐私兜底、评分全分支（正常/注入/违规/非 JSON/维度名漂移/相似度）、一致性与退化样本、MCP 握手/资源/工具/提示词/预算/坏命令、插件表单校验。
- 集成（模拟真实点击）：新建课程 → 上传细则 → 生成 → 保存并改权重 → 上传 3 份报告（含重复）→ 提取 → 打开维度详情与原文 → 勾选评分 → 等待完成 → 改等级 → 终审 → 下载 Excel → 打回重评（修改意见进提示词）→ 登记并挂载 MCP → 拉取参考并确认注入 → 切课程后状态恢复 → 上传花名册；另一条用例覆盖带插图报告的图片渲染与取图。

运行结果与矩阵见 [docs/TESTING.md](docs/TESTING.md)。

基准跑批（真实 LLM，会产生费用）：

```bash
python tests/integration/bench_run.py tests/fixtures/bench/cn_lab
```

---

## 11. 常见问题

| 现象 | 处理 |
|---|---|
| 页面能开但生成细则报错 | 检查「配置」页 Base URL/模型名/API Key；`api_key` 填的是环境变量名时确认该变量已设置 |
| 细则维度全被丢弃 | 模型没给 `doc_ref`。换更强模型重试，或在细则页手动新增维度后逐格补全 |
| 评分结果全是 C 且提示「LLM 未返回该维度」 | 模型输出不是 JSON：换模型重试；该报告也可点「打回重评」 |
| `llm_failed` 状态 | 模型未返回可解析 JSON；报告不计入成绩，可直接重评 |
| 首次 OCR 很慢 | paddleocr 首次加载/下载模型；之后走缓存 |
| Chroma 报错 | 本地库在 `data/output/sessions/<课程>/kb_db`，被其他进程占用时先关闭旧进程 |
| 插件显示「不可用」 | 看「插件」页错误列；`npx` 类插件首次运行需联网下载，HTTP 插件确认端口与路径（通常是 `/mcp`） |
| 判分与教师差异大 | 用「校准模式」上传一份教师已判的示例报告，对比分歧并改细则；也可把教师评分写入 `teacher_grades.json` 看 κ |

---

## 12. 已知限制

- 单进程内存态：同一课程只支持一位教师同时操作（评分线程有锁，但状态在进程内）。
- 相似度基于向量近邻，长报告会被截断参与比对；只做「提示」，不做自动判定抄袭。
- 报告正文送入模型的长度上限 8000 字符（超长部分不参与评分），插图上限于前 20 张描述。
- `utils/llm_client.py` 每次调用新建客户端（受保护文件），高频调用时有额外开销；如需连接复用需先解除保护。
- OCR 对手写体、拍照倾斜件效果有限。
- 一致性分析需要教师真值文件，页面不会凭空生成。

## 13. 许可

MIT，见 [LICENSE](LICENSE)。
