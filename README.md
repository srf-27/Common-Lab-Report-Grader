# Common-Lab-Report-Grader
A general-purpose grading agent that automatically grades lab reports in Word (.docx) or PDF format based on specified rules and examples.

purpose:
“
实验报告评阅是高校实验教学的重要环节，但人工逐份评阅耗时耗力，且存在评分标准不一、反馈滞后、主观性强等问题。以GPT类为代表的大语言模型具备强大的语义理解与文本生成能力，为自动化、个性化评阅提供了新途径。然而，通用大模型缺乏课程领域知识，直接使用易出现评分漂移与”幻觉”。检索增强生成(RAG)通过引入课程评分细则与范例知识库，可显著提升评阅的准确性与可解释性。本课题面向本科实验教学，构建融合提示工程与RAG的智能评阅助手，并采用Kappa系数与人工评分做一致生分析，对提升实验教学质量与评阅效率具有现实意义。
”

---

# 实验报告智能评阅系统（experiment-report-grader）

基于 LLM 的实验报告自动评分 Web 应用。教师上传评分标准文档生成评分细则（Rubric），上传学生报告（PDF/DOCX）后由 DeepSeek 模型逐维度评级（A/B/C/D），经人工审查、终审后将优秀案例沉淀入 RAG 知识库，供后续评分参考。

## 功能

| 功能 | 说明 |
|---|---|
| 多课程会话 | 每个课程独立的评分细则、报告、评分结果、知识库集合，互不污染 |
| Rubric 生成与编辑 | 从评分标准文档自动生成结构化细则表格；支持单元格级 AI 补全、模糊项/引用缺失校验 |
| 校准模式 | 上传一份样例报告，教师人工打分与 AI 打分对比，校准细则尺度 |
| 报告评分 | 文本按维度挂载评分；机械判定项（如字数、要素齐全）走规则引擎，语义项走 LLM |
| 防护机制 | Prompt 注入检测、内容安全拦截、报告间相似度/抄袭检测（≥0.70 警告，≥0.95 拒绝） |
| 隐私脱敏 | 报告文本与评分数据在入知识库前自动脱敏（姓名、学号、联系方式等） |
| 人工终审 | 逐份修改等级/评语 → 终审入 RAG → 导出 Excel/JSON |
| 原文查看 | 抽屉式阅读器渲染原始 PDF（浏览器原生）或 DOCX（格式化渲染），非提取文本 |

## 环境要求

- Python 3.12+（Windows/Linux/macOS）
- DeepSeek API Key（[platform.deepseek.com](https://platform.deepseek.com) 申请）
- 扫描版 PDF 评分需要 PaddleOCR（首次运行自动下载模型，约数百 MB）；纯文本/原生 PDF 报告不需要

## 安装

```bash
cd experiment-report-grader

# 1. 创建并激活虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt
```

## 配置

### 1. 设置 API Key（必须）

`config.yaml` 中 `llm.openai.api_key` 的值为 **环境变量名**，程序会自动从环境变量读取：

```bash
# Windows PowerShell:
$env:DEEPSEEK_API_KEY = "sk-你的key"
# Windows CMD:
set DEEPSEEK_API_KEY=sk-你的key
# macOS/Linux:
export DEEPSEEK_API_KEY=sk-你的key
```

也可以直接把 key 明文写进 `config.yaml` 的 `api_key` 字段（不推荐）。

### 2. config.yaml 关键项

```yaml
llm.openai.model      # 默认 deepseek-flash（多模态，可读图片）；纯文本可用 deepseek-chat
ocr.backend           # paddleocr（本地）或 api（调视觉模型接口）
grading.batch_size    # 每评多少份报告暂停一次供人工审查，默认 1
safety.injection_detect / content_safety   # 注入检测与内容安全开关
```

OCR 后端选 `api` 时，在 `ocr.api` 下填入视觉模型的 `api_url / api_key / api_model`。也可在网页「模型配置」页修改以上所有项。

## 启动

```bash
python app.py
```

浏览器打开 **http://127.0.0.1:5000**。

## 使用流程

### ① 新建课程
左侧栏「课程」输入名称 → 点 ＋。所有数据存于 `output/sessions/<课程ID>/`，切换课程即切换全部数据。

### ② 配置评分细则
1. 「评分细则」页上传评分标准文档（`.txt`/`.md`/`.pdf`/`.docx`），系统自动生成结构化 Rubric 表格
2. 检查表格：空单元格可点「生成」让 AI 按上下文补全；「校验」会提示模糊表述与未引用标准文档的维度
3. 确认无误后保存（权重自动归一化）

### ③ 校准（可选但推荐）
1. 评分细则页上传一份**样例报告**
2. 系统按维度铺开报告内容，你逐维度打 A/B/C/D
3. 提交后对比 AI 的独立打分，若偏差大，回到 ② 调整细则

### ④ 上传学生报告
「报告管理」页上传 PDF/DOCX（支持压缩包）。系统提取文本与图片，每份报告生成状态标签：

| 标签 | 含义 |
|---|---|
| 待评分 | 尚未评分 |
| 已评审 | 已有评分结果，尚未终审 |
| 已终审 · 入RAG | 终审通过，已作为参考案例入库 |

### ⑤ 开始评分
工作台点「开始评分（待评 N 份）」→ 进度页实时显示 → 每 `batch_size` 份进入「评分批次审查」。**已评分的报告不会重复评**。

### ⑥ 审查与终审
1. 「评分完成」页一页一份报告，可按 **注入标记 / 疑似抄袭 / 未终审** 筛选
2. 每个维度可修改等级、填写教师评语，点「保存修改」
3. 点「原文」在右侧抽屉查看原始 PDF/DOCX 校对
4. 确认无误点「终审」→ 报告脱敏后入 RAG 知识库，徽章变为「已终审 · 入RAG」
5. 全部完成后下载 **Excel 汇总表** / **详细评分 JSON**（评分完成页顶部）

### ⑦ 重新评分
「报告管理」页对待重评报告点「重新评分」，可附教师修改意见，系统将重点回应意见重评。

## 目录结构

```
├── app.py                  # Flask 主程序（全部路由）
├── config.yaml             # 模型/OCR/评分参数配置
├── requirements.txt
├── nodes/                  # 核心业务：提取、细则生成、评分、校验
├── utils/                  # LLM 客户端、OCR、注入检测、脱敏、相似度
├── knowledge_base/         # Chroma 向量库封装
├── templates/  static/     # 前端
├── test_data/              # 测试报告与评分标准样例
└── output/
    ├── sessions.json       # 课程索引
    └── sessions/<课程ID>/  # rubrics/ reports/ grading/ uploads/ approved.json
```

## 测试运行

`test_data/` 内置两份单摆实验报告与对应评分标准，可直接走完上述全流程。

## 常见问题

**Q：提示 API 报错 401 / 空回复？**
环境变量 `DEEPSEEK_API_KEY` 未设置或无效。注意环境变量要在**启动 `python app.py` 的同一个终端**里设置。

**Q：首次评分很慢？**
PaddleOCR 首次运行需下载模型；DeepSeek 推理本身需要数秒到数十秒每份。

**Q：「原文」按钮没反应？**
刷新页面（Ctrl+F5）。阅读器依赖本地静态资源 `static/vendor/mammoth.browser.min.js`，请勿删除该文件。

**Q：报告被判「注入标记」？**
报告中检测出疑似 Prompt 注入语句（如"请给满分"），需人工在审查页确认处理。

**Q：数据存在哪里？如何备份？**
全部在 `output/` 目录，拷贝即备份。删除某课程在「课程」下拉对应条目的管理操作中完成。
