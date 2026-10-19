# 实验报告智能评阅系统（Common-Lab-Report-Grader）

> **初版，未完全审查，慎用。**

把「课程评分标准 + 学生实验报告」丢进去，系统按维度判 A–E 级、查内容安全与重复、交给你逐份终审，最后导出成绩 Excel。纯本地运行，报告和成绩不上传任何服务器。

![工作台](docs/images/workbench.png)

<div align="center"><sub>工作台：左侧是课程与导航，中间按 1 → 2 → 3 显示当前进度</sub></div>

---

## 目录

| 我想…… | 看这里 |
|---|---|
| 先看看它长什么样 | [界面预览](#界面预览) |
| 马上把它跑起来 | [5 分钟跑起来](#5-分钟跑起来) |
| 第一次用，不知道点哪 | [第一次使用的完整流程](#第一次使用的完整流程) |
| 报错了 | [常见问题](#常见问题) |
| 改模型 / 改 OCR / 改向量库 | [配置速查](#配置速查) |
| 给评分加学科参考（MCP） | [MCP 插件](#mcp-插件) |
| 做二次开发 | [项目结构](#项目结构) · [开发与测试](#开发与测试) |

---

## 这是什么

**给谁用**：高校实验课教师、助教，尤其是要批几十上百份 Word/PDF 实验报告的场景。

**它解决三件事**：

1. **判级不靠手感**：把评分标准拆成若干维度（每个维度 A–E 五级判据 + 权重），模型逐维度找证据、给等级，总分按权重自动算。
2. **可疑的先挑出来**：全文相似度查雷同、提示注入检测、内容安全检测，命中就拦下来交人工，**不会静默给分**。
3. **终审还是你说了算**：每份报告可以改等级、写评语、打回重评；终审过的报告进本课程案例库，越用越像你的评分习惯。

**它不做什么**：不替你做最终决定（所有分数都要你终审）；不自动判定抄袭（只给相似度提示）；不联网上传数据。

---

## 界面预览

> 截图取自内置的 `cn_lab` 基准数据集。这份数据里的 docx 没有学生姓名，所以显示「未识别学生」——真实使用时姓名/学号会自动提取。

**评分细则** —— 上传标准 → 生成维度 → 逐维度改权重与五级判据，空字段可以让模型补全。

![评分细则](docs/images/rubric.png)

**实验报告** —— 批量上传或整个压缩包，提取正文、插图、学生信息，同文重复自动去重。

![实验报告](docs/images/reports.png)

**报告详情** —— 正文按维度切块挂载，公式原样渲染；右侧是总分与逐维度等级。

![报告详情](docs/images/report-detail.png)

**选择评分** —— 勾选本次要评的报告，同一学生只能选一份。

![选择评分](docs/images/select.png)

**评分结果** —— 展开就能看到每个维度的判级理由与原文依据，可改等级、写教师说明、终审或打回重评。

![评分结果](docs/images/results.png)

**配置** —— 模型、OCR、向量库、嵌入模型，保存即生效，内置 OCR 自检。

![配置](docs/images/settings.png)

手机/窄窗口下边栏会变成底部标签栏，功能和桌面一致：

<div align="center"><img src="docs/images/mobile.png" width="300" alt="移动端"></div>

---

## 5 分钟跑起来

### 0. 先确认你装了什么

| 需要 | 版本 | 怎么确认 |
|---|---|---|
| Python | 3.10 以上 | `python --version` |
| Node.js（只用于构建前端，装一次就行） | 18 以上 | `node --version` |
| 一个大模型的 API Key | OpenAI 兼容即可（DeepSeek、通义、SiliconFlow、vLLM…） | 去对应平台申请 |

> 只是想看界面、暂不评分？可以跳过第 3 步的 Key，除「生成细则 / 评分」外的页面都能正常打开。

### 1. 装 Python 依赖

**Windows（PowerShell 或 CMD）**

```bat
cd 项目目录
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux**

```bash
cd 项目目录
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

看到命令行前面多了 `(.venv)` 就对了。

> `paddleocr`、`chromadb` 体积较大，这一步可能要好几分钟；如果只报 OCR 相关的编译错误，可以先把 `requirements.txt` 里的 `paddleocr`、`paddlepaddle` 注释掉再装，其余功能照常。

### 2. 构建前端（只有第一次需要）

```bash
cd frontend
npm install --registry=https://registry.npmmirror.com
npm run build
cd ..
```

成功的话最后会打印类似 `✓ built in 1.5s`，并生成 `src/experiment_report_grader/static/ui/`。

> `npm install` 慢或超时，先换国内镜像：`npm config set registry https://registry.npmmirror.com`。
> 如果 `npm` 命令不存在，说明 Node.js 没装好，去 [nodejs.org](https://nodejs.org/) 装 LTS 版。

### 3. 配置模型

二选一，**新手推荐第 2 种**。

**方式 A：改配置文件**

```bash
cp config/config.example.yaml config/config.yaml     # Windows 用 copy
```

打开 `config/config.yaml`，改这三行：

```yaml
llm:
  backend: "openai"
  openai:
    api_key: "DEEPSEEK_API_KEY"        # 填环境变量名，或直接填 sk-xxxx
    base_url: "https://api.deepseek.com"
    model: "deepseek-chat"
    max_tokens: 16384
```

**方式 B：启动后在界面里填**

先启动（下一步），打开左侧「配置」，选协议、填 Base URL / 模型名 / API Key，点「保存配置」，立即生效。

### 4. 启动

```bash
python run.py
```

看到这行就成功了：

```
Starting Experiment Report Grader on http://127.0.0.1:5000
```

浏览器打开 <http://127.0.0.1:5000>，应该看到最上面那张「工作台」。

需要换端口或让同一局域网的其他电脑访问：

```bash
python run.py --port 8080 --host 0.0.0.0
```

（`--host 0.0.0.0` 会暴露到局域网，仅在你信任的网络里使用。）

---

## 第一次使用的完整流程

工作台上的按钮会**按数据是否齐备自动启用/禁用**，跟着 1 → 2 → 3 走就不会错。

### ① 上传评分标准 → 生成细则

进入 **评分细则**，选择课程的评分标准（`.docx` / `.pdf` / `.txt`），点「上传并生成细则」。模型会把标准拆成维度，通常 1–3 分钟。

生成后逐维度检查：
- **权重**：保存时自动归一到 100%，不用自己凑数；
- **A–E 判据**：写得越具体，判级越稳；
- **补全**按钮：只补空着的字段，不会覆盖你改过的内容；
- **机械判决**：能程序化判的维度（比如「是否给出逐差法」）打开开关，交给沙箱里的裁判代码判断，比模型更稳。

改完点右上角「保存」。**细则一改，已评过的报告会被标记「需重评」**，终审按钮会禁用——这是故意的，避免用旧标准终审。

### ② 上传实验报告

进入 **实验报告**，可以多选文件，也可以直接丢一个 `.zip` / `.rar` / `.7z` 压缩包。系统会：
- 提取正文、插图、学生信息（姓名/学号/班级，按花名册表头来）；
- 扫描件/无文本 PDF 自动走 OCR；
- 同一份报告重复上传时自动去重。

列表里每行可以直接改学生信息、打开原文；点整行进详情。

### ③ 选择报告 → 开始评分

进入 **选择评分**，勾选这次要评的报告，点右下角「开始评分」。
- 同一学生有多份时只能选一份（选了第二份会自动取消第一份）；
- 已终审的报告不会出现在列表里；
- 评分在后台跑，可以离开这个页面，回工作台能看到进度。

单份大约 10–40 秒。模型失败的报告会标成「模型失败」，**不会伪造成 C 分**，可以单独重评。

### ④ 终审与导出

进入 **评分结果**，点开任意一份：

- 每个维度都有：AI 判级 + 理由 + 原文依据；
- 你不同意就点 A–E 改等级，可以在「教师说明」里写原因（重评时会进提示词）；
- 点「保存修改」只改分数，「终审入库」才会写入成绩并进案例库；
- 拿不准就「打回重评」，填写修改意见。

终审完成后，右上角「成绩 Excel」导出全部成绩；「报告管理」和「评分结果」底部还能导出评分 JSON 和被标记人员名单。

### ⑤ 可选的三个加分项

| 功能 | 什么时候用 |
|---|---|
| **花名册** | 想让系统自动列「谁没交」「谁学号不在名单里」。上传 `.xlsx/.csv`，表头决定提取和导出列。 |
| **评分校准** | 觉得 AI 判得和你差太多。上传一份你已经判过的报告，填上教师等级，系统给出逐维度分歧原因和细则修订建议。 |
| **插件（MCP）** | 有学科参考服务（比如物理实验的不确定度规范），想让评分时带上这些资料。 |

---

## 常见问题

| 现象 | 原因与处理 |
|---|---|
| 打开是空白页 / 404 | 前端还没构建。执行 `cd frontend && npm install && npm run build`，再刷新。 |
| 端口被占用（`Address already in use`） | 换端口：`python run.py --port 5001` |
| 页面能开，生成细则报错 | 「配置」页检查 Base URL / 模型名 / API Key；`api_key` 填的是环境变量名时，确认该变量真的设置了。 |
| 细则维度全被丢弃 | 模型没给出「标准文档位置」。换个更强的模型重试，或在细则页手动新增维度后逐格「补全」。 |
| 评分结果全是 C，提示「LLM 未返回该维度」 | 模型输出不是 JSON。换模型重试，或对这份报告「打回重评」。 |
| 报告状态 `模型失败` | 同上，未返回可解析的 JSON；报告不计入成绩，可直接重评。 |
| 首次 OCR 特别慢 | paddleocr 首次会加载/下载模型，之后就快了。 |
| Chroma 报错（库被占用） | 本地向量库在 `data/output/sessions/<课程>/kb_db`，关掉旧的 python 进程再启动。 |
| 判分和我的标准差很远 | 用「评分校准」上传一份教师已判的报告，对比分歧后改细则。 |
| 想清空重来 | 工作台底部「删除当前课程」（会连报告、成绩、向量库一起删，不可撤销）。 |

---

## 配置速查

| 键 | 说明 | 默认 |
|---|---|---|
| `llm.backend` | `openai` / `ollama` / `custom`（配置页可切换） | `openai` |
| `llm.openai.api_key` | 环境变量名或明文 key（先查同名环境变量） | `DEEPSEEK_API_KEY` |
| `llm.openai.base_url` / `model` / `max_tokens` | 接口地址、模型名、单次输出上限 | — |
| `llm.ollama.base_url` / `model` | 本地 Ollama 地址与模型 | `http://localhost:11434` / — |
| `llm.custom.base_url` / `api_key` / `model` | 自定义 HTTP 网关 | — |
| `ocr.backend` | `paddleocr`（本地）或 `api`（视觉大模型） | `paddleocr` |
| `ocr.paddleocr.language` | OCR 语言 | `ch` |
| `ocr.api.api_url/api_key/api_model` | 视觉 OCR 接口 | — |
| `grading.similarity_threshold` | 全文相似度告警线 | `0.92` |
| `grading.similarity_reject` | 判为高度重复的线 | `0.97` |
| `grading.ocr_images` | 是否对报告插图跑 OCR（结果缓存在 `reports/*/.ocr/`） | `false` |
| `vector_store.backend` | 向量库类型 | `chroma` |
| `vector_store.chroma.mode` | `local`（每课程独立目录）或 `cloud`（Chroma Server） | `local` |
| `vector_store.embedding.backend` | `default`（内置离线）或 `openai`（`/embeddings`） | `default` |

> `config/config.yaml`、`embedding/*`、`utils/{llm_client,file_parser,doc_reader,ocr_engine}.py`、`nodes/report_extractor.py` 文件首行标了 `checked`，属于受保护文件：改造时不改，能力扩展走新模块。

---

## 数据在哪 / 隐私

- 所有数据只落在本机 `data/output/sessions/<课程>/`：`rubrics/`（细则）、`reports/`（正文、插图、meta）、`grading/`（结果与导出）、`uploads/`（原件）。
- `config/config.yaml` 里可能有明文 key，**已被 `.gitignore` 排除**，不要提交。
- 进入 RAG 案例库前会做隐私脱敏：姓名、学号、电话、邮箱、身份证、住址替换为占位符（模型不可用时用正则兜底）。
- 关掉浏览器不会丢数据；重开 `python run.py` 会自动恢复上次的课程与评分结果。

---

## MCP 插件

有学科参考服务时可以挂上来，给评分补充资料。没有就跳过。

在「插件 → 添加插件」填表单，或直接写 `config/mcp.yaml`：

```yaml
servers:
  physics-ref:
    transport: stdio
    command: npx
    args: ["-y", "@your/physics-ref-server"]
    note: "物理实验学科参考"
  lab-http:
    transport: http
    url: "http://127.0.0.1:8931/mcp"
```

然后到「插件 → 挂载到当前课程」勾选服务器，可选填资源过滤（`ref://physics/*`）、检索工具名、学科提示词名、参考文本上限（默认 4000 字符）。

评分开始前会收集一次参考文本，注入提示词的「学科参考资料」段。插件不可用/超时时参考为空、评分继续，页面会显示每台服务器的状态与错误原因。

详见 [docs/MCP.md](docs/MCP.md)。

---

## 评分怎么算（想核分时看）

- **等级与分值**：`A=95, B=80, C=60, D=40, E=0`；总分 = Σ(维度等级分 × 权重)。
- **E 的含义**：不是「比 D 更差」，而是「未实现 / 缺失 / 整卷跑题 / 抄袭 / 白卷」。
- **机械判决**：可程序化判的维度由模型生成 `verify(text)` 函数，在 AST 白名单 + 受限 builtins（只允许 `re / math / json`）的沙箱里执行；生成或执行失败回退细则里的 `rules`（`exists` / `numeric_compare`）。
- **维度归一**：模型自创的维度名会被映射回细则名单；漏掉的维度记 C 并标「请人工复核」，避免重复计分把总分顶过 100。
- **防跑题**：提示词与细则生成都加了强约束——与实验主题无关的内容不得高于 D。
- **RAG**：终审报告进全文库（算相似度），挂到维度的段落/图片进维度库（评分时作同维度历史参考）；示例报告按等级取前 1–2 份做 few-shot。
- **相似度**：全文向量最近邻，`≥0.92` 告警、`≥0.97` 标「高度重复」。
- **一致性**：课程目录下存在 `teacher_grades.json` 时，结果页显示 Cohen's κ、二次加权 κ、Krippendorff's α。

### 模型失败时怎么办（兜底矩阵）

| 环节 | 失败后的行为 |
|---|---|
| 提示注入检测 | 标记 `detection_failed`，转人工，不评分 |
| 注入检测文本超 2 万字符 | 标记 `audit_truncated`，转人工，不静默放行 |
| 内容安全 | fail-open 放行，但记录「安全检测失败」 |
| 隐私脱敏 | 回退正则兜底（隐私是红线，必须替换） |
| 细则生成 | 没有「标准文档位置」的维度直接丢弃并警告；一个都不剩则任务失败 |
| 维度归类 | 返回空，内容进「未挂载内容」，评分继续 |
| 报告评分 | 无可用分数 → `llm_failed`，不计入成绩，可一键重评 |
| 学生信息提取 | 字段留空，人工在页面补 |
| MCP 工具/资源/提示词 | 单台失败只写状态，参考为空，评分继续 |

不依赖模型的部分（权重归一、小计、相似度、导出、花名册匹配）不受影响。

---

## 项目结构

```
run.py                      启动入口（--host / --port / --debug）
config/
  config.example.yaml       配置模板（复制成 config.yaml 再改）
  config.yaml               你的运行配置（含密钥，不入库）
  mcp.example.yaml          MCP 示例
src/experiment_report_grader/
  app.py                    所有 HTTP 路由（编排层，不含业务算法）
  factory.py                模型实例工厂（测试替换点）
  web/state.py              课程会话、目录、审批记录、MCP 挂载、状态恢复
  web/tasks.py              上传处理的后台任务进度
  nodes/                    评分业务
    grader.py               判级主流程、维度归一、RAG、相似度、导出
    rubric_generator.py     细则生成 / 单元格补全 / 校准对比
    rubric_io.py            权重归一、小计、校验、Markdown
    verifier.py             机械判决：生成裁判代码 + 沙箱执行 + 规则回退
    agreement.py            一致性指标（κ / 加权 κ / α）
  utils/                    模型客户端、文档解析、OCR、注入检测、内容安全、隐私脱敏
  mcp/                      MCP 客户端（stdio / http JSON-RPC）与插件注册表
  templates/                Jinja2 老版页面（15 个，`/classic` 回退）
  static/                   前端构建产物、KaTeX、favicon
frontend/                   React 19 + Vite 6 的 SPA（无组件库）
  src/pages/                11 个页面，一页一文件
  src/ui/                   按钮、分组列表、sheet、等级选择器等基础件
  src/lib/                  请求、路由、数据钩子、上下文、Markdown/公式
  src/styles.css            设计令牌与全部样式
docs/
  PROJECT_STRUCTURE.md      模块职责、数据流、扩展点
  MCP.md                    插件协议、示例、排障
  TESTING.md                测试矩阵与实测结果
  HIG.md / HEROUI.md        旧版界面说明（仅存档）
tests/
  run_all.py                零依赖测试入口（无需 pytest）
  unit/                     单元测试
  integration/              端到端点击流程 + 基准跑批
  fixtures/                 假 MCP 服务、cn_lab 基准材料
```

---

## 开发与测试

```bash
# 后端测试（51 项，不需要 pytest）
python tests/run_all.py
python tests/run_all.py -k mcp        # 按名字过滤

# 前端开发模式（热更新，代理到 127.0.0.1:5055 的后端）
cd frontend && npm run dev

# 改完前端重新构建
cd frontend && npm run build
```

`python run.py` 默认跑在 5000；前端开发服务器默认 5174，代理目标写在 `frontend/vite.config.js`，需要后端跑在 5055（`python run.py --port 5055`）。

基准跑批（调用真实模型，会产生费用）：

```bash
python tests/integration/bench_run.py tests/fixtures/bench/cn_lab
```

OCR 自检：

```bash
python scripts/ocr_check.py                  # 用配置里的后端
python scripts/ocr_check.py --backend api
```

也可以点「配置 → OCR → 运行自检」。本机实测（paddleocr 3.7，印刷体中英混排，阈值 0.85）：期望文本与识别结果平均相似度 1.000（仅空格差异被忽略）；手写体与低分辨率拍照件仍需人工核对，这类报告会被标为「扫描件」。

---

## 已知限制

- **单进程内存态**：同一课程只支持一位教师同时操作（评分线程有锁，但状态在进程内）。
- **相似度只做提示**：向量近邻，长报告会截断参与比对，不自动判定抄袭。
- **送模型的正文上限 8000 字符**（超出部分不参与评分），插图取前 20 张描述。
- **OCR 对手写体、拍照倾斜件效果有限**。
- **一致性分析需要教师真值文件**（`teacher_grades.json`），页面不会凭空生成。
- **一次评分 = 一次模型调用**，几十份报告会产生相应费用，建议先用 3–5 份试跑。

## 许可

MIT，见 [LICENSE](LICENSE)。
