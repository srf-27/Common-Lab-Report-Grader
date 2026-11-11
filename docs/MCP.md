# MCP 插件

MCP（Model Context Protocol）服务器可以给评阅补充两类能力，都挂在**流程页**（原「插件页」已并入此页）：

1. **学科参考资料**：评分开始前拉一次参考文本，注入提示词的「学科参考资料」段（`不确定度规范`这类只读资料）。
2. **可调用的工具**：把服务器暴露的工具（`tools/list` 的 `inputSchema`）直接转成 OpenAI function-calling 的 `tools`，判级时模型**真实调用**它，结果回灌进判级理由。

没有插件也能正常评分；插件不可用或超时，参考为空、评分继续。

---

## 注册一个服务器

两种方式，等价：

- **界面**：流程页 → 添加插件，填表单。
- **文件**：复制 `config/mcp.example.yaml` 为 `config/mcp.yaml` 后编辑（`config/mcp.yaml` 已被 `.gitignore` 排除，含密钥不要提交）。

```yaml
servers:
  physics-ref:
    transport: stdio              # 本地子进程
    command: npx
    args: ["-y", "@your/physics-ref-server"]
    env:
      REF_API_KEY: "xxx"
    note: "物理实验学科参考"

  lab-http:
    transport: http               # 远程端点（Streamable HTTP / JSON-RPC）
    url: "http://127.0.0.1:8931/mcp"
    headers: {}
    note: "远程学科参考"

  markitdown:                     # 报告格式兜底转换，见下节
    transport: stdio
    command: markitdown-mcp       # pip install markitdown-mcp
    note: "html/pptx/xlsx/epub → Markdown"
```

字段：`transport`（`stdio` / `http`）必填；stdio 用 `command` + `args` + `env`，http 用 `url` + `headers`；`note` 只在界面显示。

---

## 挂到当前课程

流程页 → 挂载到当前课程，勾选要用的服务器。挂载是**按课程**保存的（`<课程>/mcp_mount`），切课互不影响。每个 LLM 节点（细则生成 / 校准 / 注入检测 / 内容安全 / 维度归类 / 判级）都可单独选择挂载哪些能力：

- `calc` —— 内置计算工具包（`calc_eval` / `calc_stats` / `calc_fit`），不依赖任何服务器；
- `skill:<名字>` —— 本机 `skills/<名字>/skill.py` 技能包（提供 `TOOLS_SCHEMA` + `dispatch`）；
- `mcp:<服务器>` —— 上面注册的 MCP 服务器的工具。

不挂载时，判级节点默认只开 `calc`（受 `grading.calc_verify` 控制）；参考资料只在课程挂载了服务器时才会去拉取。

---

## 报告格式兜底（markitdown）

本地解析器只处理 PDF/DOCX/DOC/MD。`.html` / `.pptx` / `.xlsx` / `.epub` 会经 **markitdown MCP** 转成 Markdown 再入库；插件缺席时这些文件被跳过并进「解析失败」清单，其余行为不变。

```bash
pip install markitdown-mcp
```

---

## 运行时行为与排障

| 现象 | 原因 / 处理 |
| --- | --- |
| 参考资料为空 | 当前课程没挂载服务器，或服务器 `initialize` 失败——看流程页每台的状态与错误原因。 |
| 工具没被调用 | 该 LLM 节点没勾这个 `mcp:<服务器>`；或服务器 `tools/list` 返回空。 |
| stdio 启动失败 | `command` 不在 PATH，或子进程没按 UTF-8 读写（本项目 fixture 已 `sys.stdout.reconfigure(encoding="utf-8")`，自建服务同理，MCP stdio 契约要求 UTF-8）。 |
| http 超时 | 端点没起 / 端口不对；评分不阻塞，参考留空继续。 |
| 换课忘了挂 | 挂载按课程独立，需在新课程重新勾选。 |

**单台失败只影响这一台**：它写进 `mcp_status` 的状态与错误原因，其余服务器照常收集，评分继续。页面会列出每台服务器的最近状态。
