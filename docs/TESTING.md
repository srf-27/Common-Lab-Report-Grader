# 测试

零依赖，不需要 pytest。全部端到端**调真实模型**（`config.yaml` 里的 `deepseek-flash`），断言的是**结构与状态**，不是模型吐出的原文。

```bash
python tests/run_all.py              # 全量（当前 129 项，unit 22 文件 + integration 7 文件）
python tests/run_all.py -k mcp       # 按名字过滤（匹配 path::name）
python tests/run_all.py -k grading   # 同上
```

前提：设置好 `DEEPSEEK_API_KEY`（或 `config.yaml` 里填明文 key）。`run_all.py` 会把 stdout/stderr 重配成 UTF-8（Windows GBK 控制台需要），并对每个 `test_*.py` **惰性导入后逐个跑**——所以某个模块 import 失败会在跑到它时才炸，不影响前面已通过的用例。

---

## 真模型测试基座：`tests/real_llm.py`

所有测试的公共入口，取代以前的 `FakeLLM` 关键字分流：

| 成员 | 用途 |
| --- | --- |
| `require_key()` | 没有可用 key 就直接失败，避免「静默跳过」看着像通过。 |
| `client()` | 返回真实 `LLMClient`，走 `config.yaml` 的 backend/model。 |
| `RecordingLLM` | 包住真客户端，记录 `.calls` / `.count`，并原样转发 `tools` / `tool_executor` 等 kwargs——用来断言「确实调了几次、传了什么」而不改判级标准。 |
| `CRITERIA` / `RUBRIC` / `REPORT` | 一份最小可判级的细则与样本正文。 |

替换点仍是 `factory._make`（`factory.llm(config)` 的唯一出口）。测试模块在**导入时**设置 `factory._make`，这个覆盖会带进之后导入的模块——`run_all.py` 的惰性导入顺序依赖这一点。

---

## 断言口径（改测试前先读）

真实模型有不确定性，判级措辞每次都可能不同。因此：

- ✅ 断言**结构 / 状态 / 键存在**：`status in {graded, llm_failed}`、每个维度有 `level ∈ A–E`、细则维度名非空、权重归一到 100、collection 建出来了没、Excel 有没有导出、409/CSRF 闸门是否拦住。
- ❌ 不断言模型原文，也不写死「总分 = 某个具体数字」或「维度一定叫『误差分析』」——细则维度名来自模型，用 `next(iter(scores))` 这类动态取。
- **一致性校准**、**身份提取**这类依赖模型自由发挥的断言，改为在测试里**注入确定数据**（如直接写 `state["extracted_reports"][i]["meta"]["student"]`、注入已评好的 pilot），保证可复现。
- 需要「细则已确认才能评分」的闸门测试，先注入一份 graded + teacher 已判的 pilot 再 `/pilot/confirm`（B4 门槛）。

---

## 什么时候才用桩

只有真实模型**无法可靠复现**的分支才用最小桩，其余一律真调：

- 模型返回**非 JSON** / 结构畸形 → 触发兜底（记 C、标「请人工复核」、`llm_failed`）；
- **内容安全**命中 `blocked_safety`、**注入检测** fail-open 放行、`detection_failed` / `audit_truncated` 留痕；
- 客户端**重试 / 抛错 / 超时**路径；
- OpenAI SDK 的 **streaming**、**function-calling 工具循环**、**MCP stdio 握手**这类协议机制本身。

这些桩写在**具体测试文件里**（就近的 `class FakeLLM`），不在公共基座里；公共基座只负责真调。

---

## 覆盖面

| 目录 | 内容 |
| --- | --- |
| `tests/unit/` | 客户端与计价、细则生成/归一/单元格补全、判级归一与工具循环、注入检测、内容安全、隐私、相似度、file_parser、calc/skills、流程工具带、CSRF、一致性指标等**纯逻辑**单测。 |
| `tests/integration/` | `test_user_flow.py` 完整点击流（上传→细则→校准→提取→评分→终审→导出）；`test_parallel_grading.py` 并发与工具循环；`test_session_isolation.py` 评分中切课不串扰；`test_vector_prune.py` 维度删/建 collection；`test_reset_and_delete.py` 重置/删课/清理闸门；`test_panel_findings.py` 审查整改回归；`test_csrf.py` 破坏性请求令牌。 |
| `tests/fixtures/` | `fake_mcp_server.py`（stdio 假服务，UTF-8 重配）、`bench/cn_lab/`（中文实验基准材料）。 |

---

## 基准跑批（会产生费用，手动跑）

```bash
python tests/integration/bench_run.py tests/fixtures/bench/cn_lab
```

对真实模型批量评一份基准课的全部报告，产出逐维度等级与一致性，用来观察判级质量随提示词/模型的漂移——不进 `run_all.py`（太长、太贵、不确定）。

OCR 单独自检：`python scripts/ocr_check.py`（或界面「配置 → OCR → 运行自检」）。
