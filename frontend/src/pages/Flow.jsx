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
  const [skillsText, setSkillsText] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const cfg = (data?.config?.grade || {});
    setSkillsText((cfg.skills || []).join("\n"));
  }, [data?.config]);

  usePoll(load, 3000, true);

  const nodes = data?.nodes || [];
  const gradeCfg = data?.config?.grade || {};
  const calcOn = (gradeCfg.tools || []).includes("calc");

  const saveGradeNode = async (tools) => {
    setBusy(true);
    try {
      const skills = skillsText.split("\n").map((s) => s.trim()).filter(Boolean);
      await postJSON("/flow/config", { node: "grade", tools, skills });
      await load();
      toast("判级节点配置已保存，下一轮评分生效", "ok");
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
        title="判级节点 · 可插拔配置"
        note="只改变判级这一步：可挂计算工具与教师补充要求；基础评分提示词不变"
        footer="保存后下一轮评分生效；正在跑的评分仍用旧配置。"
      >
        <div className="list-row" style={{ display: "block" }}>
          <div className="field" style={{ justifyContent: "space-between" }}>
            <span className="field-label">计算工具包（calc）</span>
            <Switch
              checked={calcOn}
              onChange={(checked) => saveGradeNode(checked ? ["calc"] : [])}
              aria-label="计算工具包"
            />
          </div>
          <p className="t-footnote c-secondary" style={{ margin: "4px 0 12px" }}>
            开启后，模型判级前可用 calc_eval / calc_stats / calc_fit 复算报告中的公式、不确定度与拟合，验算不符会写进判级理由。
          </p>
          <Field label="教师补充要求（skills，每行一条，最多 5 条）">
            {(id) => (
              <textarea
                id={id}
                className="input"
                rows={4}
                maxLength={1500}
                value={skillsText}
                placeholder={"例如：物理实验必须检查有效数字与单位\n不确定度未给置信因子按 k=2 处理"}
                onChange={(event) => setSkillsText(event.target.value)}
              />
            )}
          </Field>
          <div className="row" style={{ justifyContent: "flex-end", marginTop: 10 }}>
            <Button variant="filled" icon="check" loading={busy} onClick={() => saveGradeNode(calcOn ? ["calc"] : [])}>
              保存
            </Button>
          </div>
        </div>
      </Group>

      <McpPanel />
    </>
  );
}
