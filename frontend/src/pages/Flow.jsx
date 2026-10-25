import { useEffect, useState } from "react";
import { errorText, getJSON, postJSON } from "../lib/api";
import { useData, usePoll } from "../lib/hooks";
import { toast } from "../lib/toast";
import { Badge, Banner, Button, Field, Group, PageHead, Spinner, Switch } from "../ui";
import McpPanel from "./Mcp";

const KIND_LABEL = { mech: "机械", llm: "LLM", human: "人工" };
const STATUS_LABEL = { pending: "未开始", active: "进行中", done: "完成" };
const STATUS_TONE = { pending: "", active: "ok", done: "accent" };

export default function Flow() {
  const { data, error, loading, load } = useData("/api/flow");
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (selected == null) {
      setSelected(data?.config?.grade?.tools || ["calc"]);
    }
  }, [data?.config]);

  usePoll(load, 3000, true);

  const nodes = data?.nodes || [];
  const capabilities = data?.capabilities || [];

  const toggle = (id) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const saveGradeNode = async () => {
    setBusy(true);
    try {
      await postJSON("/flow/config", { node: "grade", tools: selected });
      await load();
      toast("判级节点能力已保存，下一轮评分生效", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHead
        title="流程"
        sub="评阅管线与各节点状态；带 ⚡ 的 LLM 节点可按需挂载工具，基础提示词与流程不可改。"
      />

      {error ? (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="danger" icon="alert">{error}</Banner>
        </div>
      ) : null}

      {loading && !data ? <Spinner label="读取流程…" /> : null}

      <Group title="评阅管线" note={`${nodes.filter((n) => n.status === "done").length}/${nodes.length} 个节点完成`}>
        {nodes.map((node, index) => (
          <div className="list-row" key={node.id} style={{ gap: 10 }}>
            <span
              className="row-title tnum"
              style={{
                width: 26, height: 26, borderRadius: node.kind === "llm" ? "50%" : 6,
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                fontSize: 12,
                background: node.kind === "llm" ? "var(--fill-2)" : "var(--fill-1)",
                color: node.status === "active" ? "var(--accent, #0a84ff)" : undefined,
                border: node.status === "active" ? "1.5px solid var(--accent, #0a84ff)" : "none",
              }}
            >
              {index + 1}
            </span>
            <span className="row-main">
              <span className="row-title" style={{ display: "flex", gap: 6, alignItems: "center" }}>
                {node.label}
                {node.pluggable ? <span title="可插拔节点">⚡</span> : null}
              </span>
              <span className="row-sub">{KIND_LABEL[node.kind]}节点</span>
            </span>
            <span className="row-wrap" style={{ gap: 6 }}>
              <Badge tone={STATUS_TONE[node.status]}>{STATUS_LABEL[node.status]}</Badge>
            </span>
          </div>
        ))}
      </Group>

      <Group
        title="判级节点 · 可挂载能力"
        note="真正可调用的工具：内置计算包 / skills 目录技能包 / 已挂载 MCP 服务器的工具"
        footer="勾选后判级模型可在 function calling 中真实调用这些工具；保存后下一轮评分生效。"
      >
        {capabilities.map((cap) => (
          <div className="list-row" key={cap.id} style={{ gap: 10 }}>
            <span className="row-main">
              <span className="row-title" style={{ display: "block" }}>{cap.label}</span>
              <span className="row-sub" style={{ display: "block", whiteSpace: "normal" }}>
                {cap.desc}
              </span>
            </span>
            <span className="row-wrap" style={{ gap: 6 }}>
              {cap.tools.length ? <Badge>{cap.tools.length} 个工具</Badge> : <Badge tone="warn">无工具</Badge>}
              <Switch
                checked={selected.includes(cap.id)}
                onChange={() => toggle(cap.id)}
                aria-label={`挂载 ${cap.label}`}
              />
            </span>
          </div>
        ))}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 10 }}>
          <Button variant="filled" icon="check" loading={busy} onClick={saveGradeNode}>
            保存判级节点能力
          </Button>
        </div>
      </Group>

      <McpPanel />
    </>
  );
}
