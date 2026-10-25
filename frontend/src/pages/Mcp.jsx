import { useEffect, useState } from "react";
import { errorText, getJSON, postEmpty, postForm } from "../lib/api";
import { useData } from "../lib/hooks";
import { toast } from "../lib/toast";
import {
  Badge,
  Banner,
  Button,
  Chip,
  Empty,
  Field,
  Group,
  IconButton,
  Segmented,
  Sheet,
  Spinner,
} from "../ui";

const label = (item) => item?.name || item?.uri || item?.title || JSON.stringify(item).slice(0, 60);

export default function McpPanel() {
  const { data, error, loading, load } = useData("/api/mcp");
  const [form, setForm] = useState({
    name: "",
    transport: "stdio",
    command: "",
    args: "",
    env: "",
    url: "",
    note: "",
  });
  const [mount, setMount] = useState({
    servers: [],
    resources: "",
    search_tool: "",
    prompt: "",
    max_chars: 4000,
  });
  const [busy, setBusy] = useState("");
  const [probe, setProbe] = useState(null);

  useEffect(() => {
    if (!data) return;
    setMount({
      servers: data.mount?.servers || [],
      resources: (data.mount?.resources || []).join("\n"),
      search_tool: data.mount?.search_tool || "",
      prompt: data.mount?.prompt || "",
      max_chars: data.mount?.max_chars || 4000,
    });
  }, [data]);

  const servers = Object.entries(data?.servers || {});
  const statusOf = (name) => (data?.status || []).find((item) => item.name === name);

  const addServer = async () => {
    if (!form.name.trim()) return toast("请填写插件名称", "danger");
    setBusy("add");
    try {
      await postForm("/mcp/add", { ...form });
      const next = await load();
      if (!next?.servers?.[form.name.trim()]) {
        toast("插件未登记：检查名称规则与连接参数", "danger");
        return;
      }
      setForm({ name: "", transport: "stdio", command: "", args: "", env: "", url: "", note: "" });
      toast("插件已登记", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy("");
    }
  };

  const removeServer = async (name) => {
    setBusy(`remove:${name}`);
    try {
      await postForm("/mcp/remove", { name });
      await load();
      toast("插件已删除", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy("");
    }
  };

  const testServer = async (name) => {
    setBusy(`test:${name}`);
    try {
      setProbe({ name, ...(await getJSON(`/mcp/test/${encodeURIComponent(name)}`)) });
    } catch (err) {
      setProbe({ name, error: errorText(err) });
    } finally {
      setBusy("");
    }
  };

  const saveMount = async () => {
    setBusy("mount");
    try {
      await postForm("/mcp/mount", {
        servers: mount.servers,
        resources: mount.resources,
        search_tool: mount.search_tool,
        prompt: mount.prompt,
        max_chars: mount.max_chars,
      });
      await load();
      toast("挂载设置已保存", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy("");
    }
  };

  const refresh = async () => {
    setBusy("refresh");
    try {
      await postEmpty("/mcp/refresh");
      await load();
      toast("已拉取插件参考", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy("");
    }
  };

  const toggleMount = (name) =>
    setMount((prev) => ({
      ...prev,
      servers: prev.servers.includes(name)
        ? prev.servers.filter((item) => item !== name)
        : [...prev.servers, name],
    }));

  return (
    <>
      <div className="row" style={{ justifyContent: "flex-end", marginBottom: 12 }}>
        <Button size="sm" icon="refresh" loading={busy === "refresh"} onClick={refresh}>
          拉取参考
        </Button>
      </div>

      {error ? (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="danger" icon="alert">
            {error}
          </Banner>
        </div>
      ) : null}

      {loading && !data ? <Spinner label="读取插件…" /> : null}

      <Group title="已登记插件" note={`${servers.length} 个 · config/mcp.yaml`}>
        {servers.length ? (
          servers.map(([name, cfg]) => {
            const status = statusOf(name);
            return (
              <div className="list-row" key={name}>
                <span className="row-main">
                  <span className="row-wrap" style={{ gap: 6 }}>
                    <span className="row-title">{name}</span>
                    <Badge outline>{cfg.transport}</Badge>
                    {status ? (
                      status.ok ? (
                        <Badge tone="ok">{status.count} 条参考</Badge>
                      ) : (
                        <Badge tone="danger">不可用</Badge>
                      )
                    ) : null}
                  </span>
                  <span className="row-sub" style={{ display: "block" }}>
                    {cfg.transport === "http"
                      ? cfg.url
                      : [cfg.command, ...(cfg.args || [])].filter(Boolean).join(" ")}
                  </span>
                  {status && !status.ok && status.error ? (
                    <span className="t-caption" style={{ color: "var(--danger)", display: "block" }}>
                      {status.error}
                    </span>
                  ) : null}
                  {cfg.note ? (
                    <span className="row-sub" style={{ display: "block" }}>
                      {cfg.note}
                    </span>
                  ) : null}
                </span>
                <Button
                  size="sm"
                  icon="search"
                  loading={busy === `test:${name}`}
                  onClick={() => testServer(name)}
                >
                  测试
                </Button>
                <IconButton
                  icon="trash"
                  label="删除插件"
                  disabled={busy === `remove:${name}`}
                  onClick={() => removeServer(name)}
                />
              </div>
            );
          })
        ) : (
          <div style={{ padding: 16 }}>
            <Empty
              icon="mcp"
              title="还没有登记插件"
              text="插件能给评分提供学科参考（资源、检索工具、提示词），不是必需的。"
            />
          </div>
        )}
      </Group>

      <Group title="添加插件" footer="stdio 会启动子进程；http 走 JSON-RPC，通常是 /mcp 路径。">
        <div className="list-row" style={{ display: "block" }}>
          <div className="grid-2">
            <Field label="名称" hint="只能用字母、数字、- _ .">
              {(id) => (
                <input
                  id={id}
                  className="input"
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                  placeholder="physics-ref"
                />
              )}
            </Field>
            <div className="field" style={{ justifyContent: "flex-start" }}>
              <span className="field-label">传输方式</span>
              <Segmented
                label="传输方式"
                value={form.transport}
                onChange={(key) => setForm({ ...form, transport: key })}
                options={[
                  ["stdio", "stdio"],
                  ["http", "http"],
                ]}
              />
            </div>
          </div>

          {form.transport === "stdio" ? (
            <div className="grid-2" style={{ marginTop: 12 }}>
              <Field label="命令" hint="例如 npx、python">
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={form.command}
                    onChange={(event) => setForm({ ...form, command: event.target.value })}
                    placeholder="npx"
                  />
                )}
              </Field>
              <Field label="参数" hint="空格分隔">
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={form.args}
                    onChange={(event) => setForm({ ...form, args: event.target.value })}
                    placeholder="-y @your/physics-ref-server"
                  />
                )}
              </Field>
              <Field label="环境变量" hint="每行一个 KEY=VALUE">
                {(id) => (
                  <textarea
                    id={id}
                    className="textarea"
                    value={form.env}
                    onChange={(event) => setForm({ ...form, env: event.target.value })}
                    placeholder="REF_API_KEY=xxx"
                  />
                )}
              </Field>
            </div>
          ) : (
            <div style={{ marginTop: 12 }}>
              <Field label="URL" hint="通常是 http://127.0.0.1:8931/mcp">
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={form.url}
                    onChange={(event) => setForm({ ...form, url: event.target.value })}
                    placeholder="http://127.0.0.1:8931/mcp"
                  />
                )}
              </Field>
            </div>
          )}

          <div style={{ marginTop: 12 }}>
            <Field label="备注">
              {(id) => (
                <input
                  id={id}
                  className="input"
                  value={form.note}
                  onChange={(event) => setForm({ ...form, note: event.target.value })}
                  placeholder="物理实验学科参考"
                />
              )}
            </Field>
          </div>
        </div>
        <div className="list-row">
          <Button variant="filled" icon="plus" loading={busy === "add"} onClick={addServer}>
            登记插件
          </Button>
        </div>
      </Group>

      <Group
        title="挂载到当前课程"
        actions={
          <Button size="sm" variant="tinted" icon="check" loading={busy === "mount"} onClick={saveMount}>
            保存
          </Button>
        }
        footer="挂载信息存在课程目录，按课程隔离；资源过滤每行一个 fnmatch 通配。"
      >
        <div className="list-row" style={{ display: "block" }}>
          <div className="field">
            <span className="field-label">选择服务器</span>
            {servers.length ? (
              <div className="row-wrap">
                {servers.map(([name]) => (
                  <Chip
                    key={name}
                    active={mount.servers.includes(name)}
                    onClick={() => toggleMount(name)}
                  >
                    {name}
                  </Chip>
                ))}
              </div>
            ) : (
              <span className="field-hint">没有可挂载的插件。</span>
            )}
          </div>

          <div className="grid-2" style={{ marginTop: 14 }}>
            <Field label="资源过滤" hint="如 ref://physics/*，留空读全部">
              {(id) => (
                <textarea
                  id={id}
                  className="textarea"
                  value={mount.resources}
                  onChange={(event) => setMount({ ...mount, resources: event.target.value })}
                />
              )}
            </Field>
            <Field label="检索工具名" hint="以 {query: 维度名} 调用">
              {(id) => (
                <input
                  id={id}
                  className="input"
                  value={mount.search_tool}
                  onChange={(event) => setMount({ ...mount, search_tool: event.target.value })}
                  placeholder="search_reference"
                />
              )}
            </Field>
            <Field label="学科提示词名" hint="调用 prompts/get">
              {(id) => (
                <input
                  id={id}
                  className="input"
                  value={mount.prompt}
                  onChange={(event) => setMount({ ...mount, prompt: event.target.value })}
                />
              )}
            </Field>
            <Field label="参考文本上限（字符）" hint="200–20000">
              {(id) => (
                <input
                  id={id}
                  className="input tnum"
                  type="number"
                  min="200"
                  max="20000"
                  value={mount.max_chars}
                  onChange={(event) => setMount({ ...mount, max_chars: event.target.value })}
                />
              )}
            </Field>
          </div>
        </div>
      </Group>

      <Group
        title="上次注入的参考"
        note={data?.referenced ? `${data.referenced.length} 字符` : "还没有拉取过"}
        actions={
          <Button size="sm" icon="refresh" loading={busy === "refresh"} onClick={refresh}>
            重新拉取
          </Button>
        }
        footer="评分开始前会自动收集一次；也可以手动拉取，确认插件真的返回了有用的参考。"
      >
        <div className="list-row" style={{ display: "block" }}>
          {data?.referenced ? (
            <pre
              className="prose"
              style={{
                whiteSpace: "pre-wrap",
                margin: 0,
                maxHeight: 300,
                overflow: "auto",
                fontSize: 12.5,
                fontFamily: "var(--mono)",
                background: "var(--fill)",
                borderRadius: 10,
                padding: 12,
              }}
            >
              {data.referenced}
            </pre>
          ) : (
            <p className="t-subhead c-secondary">暂无参考文本。</p>
          )}
        </div>
      </Group>

      <Sheet
        open={Boolean(probe)}
        title={probe ? `${probe.name} 的能力` : ""}
        text={probe?.server ? `server：${JSON.stringify(probe.server)}` : ""}
        onClose={() => setProbe(null)}
        wide
        footer={
          <Button variant="filled" onClick={() => setProbe(null)}>
            关闭
          </Button>
        }
      >
        {probe?.error ? (
          <Banner tone="danger" icon="alert">
            {probe.error}
          </Banner>
        ) : (
          <div className="stack">
            {[
              ["工具", probe?.tools],
              ["资源", probe?.resources],
              ["提示词", probe?.prompts],
            ].map(([title, list]) => (
              <div key={title}>
                <div className="field-label" style={{ marginBottom: 6 }}>
                  {title}（{(list || []).length}）
                </div>
                <div className="row-wrap">
                  {(list || []).length ? (
                    list.map((item, index) => (
                      <Badge key={index} outline>
                        {label(item)}
                      </Badge>
                    ))
                  ) : (
                    <span className="field-hint">无</span>
                  )}
                </div>
              </div>
            ))}
            {probe?.errors?.length ? (
              <Banner tone="warn" icon="alert">
                {probe.errors.join("；")}
              </Banner>
            ) : null}
          </div>
        )}
      </Sheet>
    </>
  );
}
