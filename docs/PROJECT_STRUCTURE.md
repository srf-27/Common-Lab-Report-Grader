# 项目结构

一句话：**Flask 后端做编排，逻辑落在 `nodes/` 与 `utils/`；React SPA 前端只调 JSON 路由；一切持久化统一走 `storage.py`（本地文件 / PostgreSQL 双后端）。**

---

## 数据流（一门课的一生）

```
上传标准 ─▶ 细则生成 ─▶ 样本校准(确认) ─▶ 上传报告(提取) ─▶ 选择评分 ─▶ 逐份判级 ─▶ 终审 ─▶ 导出
   │           │             │                │                          │           │        │
   │      rubric_generator  agreement      report_extractor          grader.py    approve  rubric_io
   │      (rubric_io 归一)  (pilot/*)      (file_parser/doc_reader)  (RAG/相似度)  入库     (Excel)
   ▼
config/mcp.yaml + skills/ ── 各 LLM 节点按需挂载 calc / skill / mcp 工具（function calling）
```

- **细则**：`rubric_generator` 让模型把标准文档拆成维度（A–E 判据 + 权重），`rubric_io` 归一权重、校验、渲染 Markdown。
- **校准**：≤5 份样本，模型与教师各评一次，`agreement` 算 κ / 加权 κ / α；确认后才允许正式评分（`app._rubric_confirmed` 是闸门）。
- **提取**：`report_extractor` + `utils/file_parser` / `doc_reader` 抽正文、表格、插图、学生信息（`student_fields`）；扫描件走 `ocr_engine`；非常见格式经 markitdown MCP 兜底。
- **判级**：`grader.py` 逐维度找证据判 A–E；注入检测 / 内容安全并行前置，维度归类与判级并行；RAG 相似度、隐私脱敏、计算验算都在这里。
- **终审/导出**：改等级、写教师说明、`approve` 入库并把本份判级作为后续范例；`rubric_io` 出成绩 Excel。

---

## 模块职责

```
run.py                              启动入口（--host / --port / --debug）
config/
  config.example.yaml               配置模板（复制成 config.yaml 再改，含密钥不入库）
  mcp.example.yaml                  MCP 注册表模板（复制成 mcp.yaml）
src/experiment_report_grader/
  app.py                            所有 HTTP 路由，只做编排；/api/flow 流程页、/pilot/* 校准、
                                    /mcp/* 插件、终审与导出都在这里串起来
  factory.py                        模型实例工厂 llm(config) → MeteredLLM（测试的唯一替换点）
  storage.py                        统一持久化入口：本地文件 / PostgreSQL 双后端，PG 不可用静默降级
  nodes/                            评分业务（纯逻辑，不碰 HTTP）
    grader.py                       判级主流程、维度归一、RAG、相似度、function-calling 工具循环
    rubric_generator.py             细则生成 / 单元格补全 / 校准对比
    rubric_io.py                    权重归一、小计、校验、Markdown、成绩 Excel 导出
    agreement.py                    一致性指标（Cohen κ / 加权 κ / Krippendorff α）
    external_scores.py              课外维度成绩单：解析、按学号合并、重算小计
    report_extractor.py             报告正文/表格/插图/学生信息提取，OCR 与解析失败归档
  utils/                            基础设施
    llm_client.py                   OpenAI 兼容客户端（重试 / 超时 / usage 统计）
    calc_tools.py                   内置计算工具包 calc_eval / calc_stats / calc_fit（OpenAI tools 契约）
    skills.py                       技能包加载器：skills/<名>/skill.py 提供 TOOLS_SCHEMA + dispatch
    file_parser.py / doc_reader.py  DOCX/PDF/MD/压缩包 → Markdown，表格与图片
    ocr_engine.py / ocr_check.py    扫描件 OCR（paddleocr / 视觉 API）与自检
    injection_detector.py           提示注入检测
    content_safety.py               内容安全检测
    privacy.py                      进 RAG 前的隐私脱敏（正则兜底）
    safe_error.py                   对外错误信息统一打码（不回显绝对路径 / 密钥）
    student_fields.py               学生身份字段（学号/姓名/班级）按花名册表头归一
  web/                              会话与运营支撑
    state.py                        课程会话、目录、审批记录、MCP 挂载、花名册、状态恢复
    tasks.py                        上传/生成等后台任务的进度机
    usage.py / pricing.py / balance.py  token 用量、四槽计价（对齐 cc-switch）、账户余额校准
  mcp/
    client.py                       MCP JSON-RPC 客户端（stdio 子进程 + http），只实现评分用到的方法
    store.py                        服务器注册表读写 config/mcp.yaml（挂载在会话目录，不在这）
  static/                           前端构建产物、KaTeX、favicon（由 frontend 构建生成）
frontend/                           React 19 + Vite 6 的 SPA（无组件库）
  src/pages/                        14 个页面，一页一文件（含流程页 Flow.jsx）
  src/ui/                           按钮、分组列表、sheet、等级选择器等基础件
  src/lib/                          请求、路由、数据钩子、上下文、Markdown/公式
  src/styles.css                    设计令牌与全部样式
skills/                             可选技能包目录：chem_calc/（skill.py + SKILL.md）
scripts/                            ocr_check.py 独立自检、view_kb.py 向量库查看
docs/                               本目录：MCP.md / PROJECT_STRUCTURE.md / TESTING.md / 运行链路图.drawio
```

---

## 扩展点（想加东西先看这里）

- **加一个判级时可调用的工具**：三选一，都不改判级主流程——
  1. 内置：往 `utils/calc_tools.py` 的 `_IMPL` / `TOOLS_SCHEMA` 添一项；
  2. 技能包：新建 `skills/<名>/skill.py`，导出 `TOOLS_SCHEMA` 与 `dispatch(name, args)`（配 `SKILL.md` 首段做描述）；
  3. MCP：在流程页注册服务器并挂载，工具自动桥接。
  然后在流程页对应 LLM 节点勾选它。契约见 `nodes/grader.py` 的工具循环与 `app._node_toolbelt`。
- **加/改一个页面**：`frontend/src/pages/` 加一页，`app.jsx` 挂路由，后端在 `app.py` 加 `/api/...` JSON 路由；改完 `cd frontend && npm run build` 生成 `static/ui/`。
- **换持久化后端**：只碰 `storage.py`；业务层都通过它读写，PG 与本地文件行为对齐。
- **换模型/供应商**：`config.yaml` 的 `llm.*` 或界面配置页，`factory.llm()` 是唯一出口。
- **一致性指标**：`nodes/agreement.py`，校准页展示的就是它算出来的。
