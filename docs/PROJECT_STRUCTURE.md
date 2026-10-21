# 项目结构说明

> 模块职责、数据流与扩展点。使用方法见 [README](../README.md)，插件见 [MCP.md](MCP.md)，测试见 [TESTING.md](TESTING.md)。

## 顶层

```
run.py                  启动入口（--host / --port / --debug）
pyproject.toml          项目元数据与依赖
requirements.txt        pip 依赖清单
frontend/               前端源码（React 19 + Vite 6，无组件库），构建产物写到 static/ui/
config/                 运行配置（config.yaml 含密钥，已 gitignore）与插件注册表 mcp.yaml
src/                    源码（src-layout）
tests/                  测试（run_all.py 零依赖入口、unit、integration、fixtures）
scripts/                辅助脚本（view_kb.py 查看向量库、ocr_check.py 验 OCR）
docs/                   本文档目录
data/output/sessions/   运行时数据（课程目录，gitignore）
output/                 历史遗留输出，可手工删除
```

## 包结构

```
experiment_report_grader/
├── app.py                     路由与编排（约 700 行）：会话、细则、报告、评分、终审、导出、配置、插件
├── factory.py                 LLM 工厂：llm(config) → LLMClient；测试通过替换 _make 注入假模型
├── web/
│   ├── state.py               课程会话与全局状态：目录、sessions.json、approved.json、mcp.json、
│   │                          花名册、hydrate_session（按目录重建内存态，含图片列表与评分结果）
│   └── tasks.py               上传处理的后台任务进度（start/update/cancel/finish/running）
├── nodes/
│   ├── grader.py              判级主流程
│   │                          · _check_similarity / _remember_report：全文相似度与入库
│   │                          · _dimension_references / _exemplar_shots：维度 RAG 与 few-shot
│   │                          · _verify_mechanical：机械判决（verifier → rules 回退）
│   │                          · assign_items：文本/图片一次性归维度（失败返回空）
│   │                          · grade_single：注入 → 安全 → 相似度 → 判级 → 归一 → 小计
│   │                          · finalize_report：终审入 RAG（批量脱敏，一次 LLM 调用）
│   │                          · export_results / export_excel：JSON 与成绩表（含可疑/缺交 sheet）
│   ├── rubric_generator.py    结构化细则生成、单元格补全、偏差校验、校准对比（全部返回结构化 JSON）
│   ├── rubric_io.py           new_criterion / normalize_weights / compute_subtotals /
│   │                          check_vague_and_refs / criteria_to_markdown / LEVEL_POINTS
│   ├── verifier.py            机械判裁判：LLM 生成 verify(text) → AST 白名单校验 → 受限 builtins 执行；
│   │                          失败回退 verify(text, rules) 正则解释器
│   ├── agreement.py           Cohen's κ / 二次加权 κ / Krippendorff's α + 混淆计数
│   └── report_extractor.py    报告解析调度（压缩包递归、按扩展名分派）— 受保护
├── utils/
│   ├── llm_client.py          OpenAI / Ollama / custom 客户端 — 受保护
│   ├── file_parser.py         PDF（pymupdf4llm 版面分析）/ DOCX（含表格与图片顺序）/ MD / 压缩包 — 受保护
│   ├── doc_reader.py          老式 .doc（OLE2 piece table + 图片签名切分）— 受保护
│   ├── ocr_engine.py          OCREngine 单例：paddleocr 2/3 与视觉 API 两种后端 — 受保护
│   ├── ocr_check.py           合成图 → 识别 → 相似度（配置页按钮与 scripts/ocr_check.py 共用）
│   ├── injection_detector.py  LLM 语义检测；不可见字符规范化 + 扫描摘要；失败转人工
│   ├── content_safety.py      LLM 语义检测；失败 fail-open 并标记
│   └── privacy.py             LLM 实体提取替换；失败回退正则
├── mcp/
│   ├── client.py              JSON-RPC 2.0 客户端（stdio 子进程 / http + SSE），
│   │                          initialize、tools、resources、prompts；collect() 按挂载拉参考
│   └── store.py               config/mcp.yaml 读写、表单校验
└── static/
    ├── ui/                    SPA 构建产物（Vite 输出，gitignore）
    └── vendor/                KaTeX（公式渲染）
```

## 前端（SPA）

`/` 与 `/app/*` 只由 React 单页应用承载；旧的 Jinja 页面已全部退役，`/classic`、`/rubric_review` 等历史路径 302 到对应的 SPA 页面。

```
frontend/
├── package.json             react 19 / vite 6（无 UI 组件库）
├── vite.config.js           base=/static/ui/，产物直出 src/experiment_report_grader/static/ui
└── src/
    ├── app.jsx              侧栏 / 移动端底部标签栏 + 路由分发
    ├── main.jsx             应用入口与全局 Provider
    ├── ui/index.jsx         按钮、分组列表、Sheet、LevelPicker、Badge 等基础件
    ├── lib/
    │   ├── router.jsx       usePath / navigate / matchRoute（history API，无路由库）
    │   ├── api.js           getJSON / postForm / postFormJSON / postJSON / postEmpty
    │   ├── hooks.js         useData / usePoll / useMedia 等
    │   ├── store.jsx        课程会话与 bootstrap 上下文
    │   └── markdown.jsx     Markdown + 表格 + KaTeX 公式
    └── pages/               13 个页面：Workbench、Rubric、Reports、ReportDetail、Select、
                             Progress、Results、Roster、Calibration、Settings、Mcp、Usage、VectorStore
```

写操作复用 Flask 的表单端点（`/upload_criteria`、`/start_grading`、`/update_scores` 等），
页面数据走只读的 `/api/*`，避免同一业务逻辑写两遍。

## 数据流

```
评分标准文档 ──(process_criteria)──> RubricGenerator.generate_structured
                                      └─> rubric_current.json / rubric_latest.md / criteria_doc.txt

报告文件 ──(process_reports)──> ReportExtractor
        ├─ reports/<stem>/text.md        正文（逐页/逐段）
        ├─ reports/<stem>/images/        图片（按出现顺序命名，含上下文标签）
        ├─ reports/<stem>/meta.json      页数、图片数、学生信息、提取时间
        └─ 同文本哈希去重（保留先上传者）

评分 ──(start_grading)──> 线程池并行 _grade_one（默认 3 路，ERG_GRADING_WORKERS 可调）
        ├─ 图片/段落一次性 assign_items → text_assignments / image_assignments
        ├─ Grader.grade_single
        │   ├─ detect_injection  → 命中：flagged_injection（不评分）
        │   ├─ check_content_safety → 命中：blocked_safety（不评分）
        │   ├─ _check_similarity → similarity_warnings
        │   ├─ _verify_mechanical → 机械维度直接定级
        │   ├─ 组装 GRADING_PROMPT（维度 + RAG 参考 + 插件参考 + 正文 8000 字 + 图片说明）
        │   ├─ _parse_json → 失败：llm_failed
        │   └─ _normalize_scores + compute_subtotals
        ├─ MCP 参考：本轮开始前 collect 一次（不是每份一次）
        └─ 结束：grading_results.json + grading_summary.xlsx + flagged_students.xlsx

终审 ──(approve_report)──> finalize_report
        ├─ 全文 + 判定 JSON → 全文库（脱敏后）
        └─ 维度段落/图片 → dim_<hash> 维度库

下轮评分 ──> _dimension_references / _exemplar_shots 读回，形成闭环
```

## 文件系统布局（每门课）

```
data/output/sessions/<课程ID>/
├── sessions.json            （在 data/output 下）课程索引与当前课程
├── rubrics/                 rubric_current.json / rubric_latest.md / criteria_doc.txt
├── uploads/                 用户上传原件（含 calibration_ 前缀的校准报告）
├── reports/<stem>/          text.md、images/、meta.json、.ocr/（开启插图 OCR 时的缓存）
├── grading/                 grading_results.json、grading_summary.xlsx、flagged_students.xlsx
├── kb_db/                   Chroma 本地库（全文 + 各维度 collection）
├── approved.json            已终审报告 ID
├── roster.json              花名册（headers + rows）
├── mcp.json                 本课程挂载的插件与参考预算
└── teacher_grades.json      （可选）教师真值，用于一致性分析
```

## 扩展点

| 想做的事 | 改哪里 |
|---|---|
| 换模型/换网关 | 「配置」页或 `config.yaml` 的 `llm`；不改代码 |
| 加一个学科知识源 | 写/接一个 MCP 服务，在「插件」页登记并挂载；不改代码 |
| 换向量库 | 实现 `embedding/base.py::VectorStoreBase` 的子类，在 `nodes/grader.py` 的客户端选择处接入；`base.py` 本身受保护但可新增子类文件 |
| 换嵌入模型 | 「配置」页 `embedding.backend=openai` + 模型名 |
| 加机械判决规则类型 | `nodes/verifier.py::_verify_one` 增加分支，并在细则生成提示词里同步允许的 type |
| 改评分提示词 | `nodes/grader.py::GRADING_PROMPT`（保持 JSON 输出契约） |
| 加页面 | `frontend/src/pages/` 新建页面 + `app.jsx` 的 `Page` 与 `NAV` |
| 改判级分值 | `nodes/rubric_io.py::LEVEL_POINTS`（导出与一致性同步生效） |

## 受保护文件（文件首行 `checked`）

`config/config.yaml`、`config/config.example.yaml`、`embedding/{base,chroma,__init__}.py`、
`nodes/report_extractor.py`、`utils/{doc_reader,file_parser,llm_client,ocr_engine}.py`

改造时不直接修改；能力扩展通过新模块或调用完成（例如 OCR 自检放在 `utils/ocr_check.py`，图片 OCR 开关放在 `app.py` 的 `_image_entries`）。
