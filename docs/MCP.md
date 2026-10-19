# MCP 插件接入

评分时可以用 MCP 服务提供的学科资料（reference）辅助判级。插件按课程挂载，互不污染；插件不可用时评分照常进行。

## 1. 协议与传输

实现 JSON-RPC 2.0，支持两种传输：

| 传输 | 配置 | 说明 |
|---|---|---|
| stdio | `command` + `args` + `env` | 启动子进程，按行读写 JSON；`initialize` 后发 `notifications/initialized` |
| http | `url` + `headers` | POST JSON-RPC；响应为 `application/json` 或 `text/event-stream`（取 `data:` 行），回传 `Mcp-Session-Id` |

已实现方法：

- `initialize`（协议版本 `2024-11-05`）
- `tools/list`、`tools/call`
- `resources/list`、`resources/read`
- `prompts/list`、`prompts/get`

超时：单次调用 25 秒（`mcp/client.py::CALL_TIMEOUT`），兼顾 `npx` / Python 子进程冷启动。

## 2. 登记

「插件 → 添加插件」或直接编辑 `config/mcp.yaml`：

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

名称只允许字母、数字、`-` `_` `.`。

## 3. 挂载

「插件 → 挂载到 <课程>」：

| 字段 | 语义 |
|---|---|
| 勾选服务器 | 参与本课程评分的插件 |
| 资源过滤 | 每行一个 `fnmatch` 通配，如 `ref://physics/*`；留空读全部 |
| 检索工具名 | 工具名，参数固定为 `{"query": "<本课程维度名>"}`，取返回的 `content[].text` |
| 学科提示词名 | `prompts/get` 的名字，参数 `{"topic": "<维度名>"}`，取 `messages[].content` |
| 参考文本上限 | 注入提示词的字符预算（200–20000） |

挂载写入 `data/output/sessions/<课程>/mcp.json`；切换课程不会串用。

## 4. 注入位置与顺序

评分开始时（`_spawn_grading`）调用一次 `mcp/client.py::collect`，按挂载顺序拼接：

```
### 插件：<名称>
【<资源名或 uri>】
<resources/read 的 text>

【检索 <tool>】
<tools/call 的 text>

【学科指引】
<prompts/get 的 messages>
```

总长受 `max_chars` 截断，随后填入评分提示词的「学科参考资料（插件提供，仅作事实核对）」段。提示词同时明确：参考材料用于事实核对，不得据此臆造证据。

## 5. 失败兜底

| 情况 | 行为 |
|---|---|
| 服务器未登记 | 状态 `不可用`，错误「服务器未在配置中登记」；参考为空 |
| 子进程起不来/退出 | 状态 `不可用`，错误含原因；参考为空 |
| 调用超时 | 单次 25 秒后判超时；该插件本轮跳过 |
| `tools/call` 报错 | 仅该工具段落缺失，资源段落仍可用 |
| `resources/read` 单条失败 | 该条缺失，其余继续 |
| `prompts/get` 失败 | 提示词段落缺失，其余继续 |

以上任一情况都不会中断评分；「插件」页与结果页展示状态表（可用/不可用、条目数、错误）。评分提示词里参考为空时显示「（无插件参考）」。

## 6. 自测

```bash
python tests/run_all.py -k mcp
```

测试用一个自带的最小服务 `tests/fixtures/fake_mcp_server.py` 覆盖握手、资源、工具、提示词、预算截断、坏命令兜底。

手工联调：

```bash
# 终端 1：跑一个最小 MCP 服务（行分隔 JSON-RPC）
python tests/fixtures/fake_mcp_server.py

# 终端 2：直接看能力清单
python - <<'PY'
import sys; sys.path.insert(0,'src')
from experiment_report_grader.mcp import client
print(client.describe({"transport":"stdio","command":sys.executable,
                       "args":["tests/fixtures/fake_mcp_server.py"]}))
PY
```

HTTP 插件同理，把 `{"transport":"http","url":"http://127.0.0.1:8931/mcp"}` 传给 `describe` 即可。

## 7. 编写自己的学科参考服务

最小可用形态（stdio，Python 标准库即可）：

```python
import json, sys

DOCS = {"ref://physics/uncertainty": "A 类按贝塞尔公式，B 类按仪器允差/√3。"}

def handle(method, params):
    if method == "initialize":
        return {"protocolVersion": "2024-11-05", "capabilities": {"resources": {}},
                "serverInfo": {"name": "my-refs", "version": "0.1"}}
    if method == "resources/list":
        return {"resources": [{"uri": u, "name": u.rsplit("/", 1)[-1]} for u in DOCS]}
    if method == "resources/read":
        return {"contents": [{"uri": params["uri"], "text": DOCS[params["uri"]]}]}
    raise KeyError(method)

for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    try:
        out = {"jsonrpc": "2.0", "id": msg["id"], "result": handle(msg["method"], msg.get("params") or {})}
    except Exception as e:
        out = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32000, "message": str(e)}}
    print(json.dumps(out, ensure_ascii=False), flush=True)
```

若要支持「按知识点检索」，再实现 `tools/list` 与 `tools/call`（工具名填到挂载表单的「检索工具名」）。
