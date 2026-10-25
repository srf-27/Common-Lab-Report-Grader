import { useEffect, useState } from "react";
import { errorText, postEmpty, postForm, postJSON } from "../lib/api";
import { useData } from "../lib/hooks";
import { toast } from "../lib/toast";
import {
  Badge,
  Banner,
  Button,
  Field,
  Group,
  PageHead,
  Segmented,
  Spinner,
  Switch,
} from "../ui";

const BACKEND_HINT = {
  openai: "DeepSeek、通义、SiliconFlow、vLLM 等 OpenAI 兼容接口",
  ollama: "本机或内网 Ollama 服务",
  custom: "自定义 HTTP 网关，需与 OpenAI 协议一致",
};

function fromData(data) {
  const llm = data.llm || {};
  const ocr = data.ocr || {};
  const vs = data.vectorStore || {};
  const chroma = vs.chroma || {};
  const emb = vs.embedding || {};
  return {
    llm_backend: llm.backend || "openai",
    base_url: llm.openai?.base_url || "",
    model: llm.openai?.model || "",
    api_key: "",
    max_tokens: llm.openai?.max_tokens || 2048,
    ollama_base_url: llm.ollama?.base_url || "",
    ollama_model: llm.ollama?.model || "",
    custom_base_url: llm.custom?.base_url || "",
    custom_model: llm.custom?.model || "",
    custom_api_key: "",
    ocr_backend: ocr.backend || "paddleocr",
    ocr_api_url: ocr.api?.api_url || "",
    ocr_api_key: "",
    ocr_api_model: ocr.api?.api_model || "",
    vs_backend: vs.backend || "chroma",
    vs_mode: chroma.mode || "local",
    vs_host: chroma.host || "",
    vs_port: chroma.port || 8000,
    vs_ssl: Boolean(chroma.ssl),
    vs_token: "",
    emb_backend: emb.backend || "default",
    emb_url: emb.openai?.base_url || "",
    emb_key: "",
    emb_model: emb.openai?.model || "",
    grading_workers: data.grading?.workers ?? 3,
  };
}

const keyHint = (configured) => (configured ? "已设置，留空保持不变" : "尚未设置");

export default function Settings() {
  const { data, error, loading, load } = useData("/api/settings");
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [check, setCheck] = useState(null);
  const [profileName, setProfileName] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);

  useEffect(() => {
    if (data) setForm(fromData(data));
  }, [data]);

  const set = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  if (loading && !data) return <Spinner label="读取配置…" />;
  if (!form) {
    return (
      <Banner tone="danger" icon="alert">
        {error || "配置读取失败"}
      </Banner>
    );
  }

  const save = async () => {
    setBusy(true);
    try {
      await postForm("/settings", { ...form, vs_ssl: form.vs_ssl ? "true" : "false" });
      await load();
      toast("配置已保存并生效", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  const runOcrCheck = async () => {
    setBusy(true);
    setCheck(null);
    try {
      setCheck(await postEmpty("/settings/ocr_check"));
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  const applyProfile = async (name) => {
    setProfileBusy(true);
    try {
      await postJSON("/llm/profile/apply", { name });
      await load();
      toast(`已切换到方案「${name}」，立即生效`, "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setProfileBusy(false);
    }
  };

  const saveProfile = async () => {
    const name = profileName.trim();
    if (!name) return toast("请先填写方案名", "danger");
    setProfileBusy(true);
    try {
      await postJSON("/llm/profile/save", { name });
      setProfileName("");
      await load();
      toast(`已把当前配置另存为方案「${name}」`, "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setProfileBusy(false);
    }
  };

  const deleteProfile = async (name) => {
    setProfileBusy(true);
    try {
      await postJSON("/llm/profile/delete", { name });
      await load();
      toast(`已删除方案「${name}」`, "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setProfileBusy(false);
    }
  };

  return (
    <>
      <PageHead
        title="配置"
        sub="保存即写入 config/config.yaml 并立即生效；密钥只在填了新值时覆盖。"
        actions={
          <Button variant="filled" icon="check" loading={busy} onClick={save}>
            保存配置
          </Button>
        }
      />

      {error ? (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="danger" icon="alert">
            {error}
          </Banner>
        </div>
      ) : null}

      <Group
        title="模型方案"
        note="多套配置一键切换"
        footer="「另存当前为方案」会把下方当前生效的模型配置存为命名方案；「应用」立即切换（正在跑的评分下一轮生效）。"
      >
        {(data.profiles || []).length === 0 ? (
          <div className="list-row">
            <span className="c-secondary">还没有保存的方案——配置好模型后点「另存当前为方案」。</span>
          </div>
        ) : (
          (data.profiles || []).map((p) => (
            <div className="list-row" key={p.name} style={{ gap: 8 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="row-wrap" style={{ gap: 8 }}>
                  <span className="t-body">{p.name}</span>
                  {data.activeProfile === p.name ? <Badge tone="ok">当前</Badge> : null}
                </div>
                <span className="t-footnote c-secondary">
                  {p.backend} · {p.model || "未填模型名"}
                </span>
              </div>
              <Button
                size="sm"
                disabled={profileBusy || data.activeProfile === p.name}
                onClick={() => applyProfile(p.name)}
              >
                应用
              </Button>
              <Button size="sm" variant="ghost" disabled={profileBusy} onClick={() => deleteProfile(p.name)}>
                删除
              </Button>
            </div>
          ))
        )}
        <div className="list-row" style={{ gap: 8, paddingTop: 10 }}>
          <input
            className="input"
            style={{ maxWidth: 220 }}
            value={profileName}
            maxLength={40}
            placeholder="方案名，如 DeepSeek-生产"
            onChange={(event) => setProfileName(event.target.value)}
          />
          <Button size="sm" icon="save" loading={profileBusy} onClick={saveProfile}>
            另存当前为方案
          </Button>
        </div>
      </Group>

      <Group title="模型" note={data.backendLabel || ""} footer={BACKEND_HINT[form.llm_backend]}>
        <div className="list-row" style={{ display: "block", paddingTop: 14, paddingBottom: 14 }}>
          <Segmented
            label="模型协议"
            value={form.llm_backend}
            onChange={(key) => set("llm_backend", key)}
            options={["openai", "ollama", "custom"]
              .filter((key) => data.backends?.[key])
              .map((key) => [key, data.backends[key]])}
          />
        </div>

        {form.llm_backend === "openai" ? (
          <div className="list-row" style={{ display: "block" }}>
            <div className="grid-2">
              <Field label="Base URL" hint="例如 https://api.deepseek.com">
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={form.base_url}
                    onChange={(event) => set("base_url", event.target.value)}
                    placeholder="https://api.deepseek.com"
                  />
                )}
              </Field>
              <Field label="模型名">
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={form.model}
                    onChange={(event) => set("model", event.target.value)}
                    placeholder="deepseek-chat"
                  />
                )}
              </Field>
              <Field label="API Key" hint={keyHint(Boolean(data.llm?.openai?.api_key))}>
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    type="password"
                    value={form.api_key}
                    onChange={(event) => set("api_key", event.target.value)}
                    placeholder="环境变量名或明文 key"
                    autoComplete="off"
                  />
                )}
              </Field>
              <Field label="单次输出上限 max_tokens">
                {(id) => (
                  <input
                    id={id}
                    className="input tnum"
                    type="number"
                    value={form.max_tokens}
                    onChange={(event) => set("max_tokens", event.target.value)}
                  />
                )}
              </Field>
            </div>
          </div>
        ) : null}

        {form.llm_backend === "ollama" ? (
          <div className="list-row" style={{ display: "block" }}>
            <div className="grid-2">
              <Field label="Base URL">
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={form.ollama_base_url}
                    onChange={(event) => set("ollama_base_url", event.target.value)}
                    placeholder="http://localhost:11434"
                  />
                )}
              </Field>
              <Field label="模型名">
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={form.ollama_model}
                    onChange={(event) => set("ollama_model", event.target.value)}
                    placeholder="qwen2.5:14b"
                  />
                )}
              </Field>
            </div>
          </div>
        ) : null}

        {form.llm_backend === "custom" ? (
          <div className="list-row" style={{ display: "block" }}>
            <div className="grid-2">
              <Field label="Base URL">
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={form.custom_base_url}
                    onChange={(event) => set("custom_base_url", event.target.value)}
                  />
                )}
              </Field>
              <Field label="模型名">
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={form.custom_model}
                    onChange={(event) => set("custom_model", event.target.value)}
                  />
                )}
              </Field>
              <Field label="API Key" hint={keyHint(Boolean(data.llm?.custom?.api_key))}>
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    type="password"
                    value={form.custom_api_key}
                    onChange={(event) => set("custom_api_key", event.target.value)}
                    autoComplete="off"
                  />
                )}
              </Field>
            </div>
          </div>
        ) : null}
      </Group>

      <Group
        title="OCR"
        note="PDF 无文本时自动识别"
        footer="本地 OCR 首次调用会加载或下载模型，比较慢；手写体与倾斜拍照件仍需人工核对。插图 OCR 由 config.yaml 的 grading.ocr_images 控制。"
        actions={
          <Button size="sm" icon="refresh" loading={busy} onClick={runOcrCheck}>
            运行自检
          </Button>
        }
      >
        <div className="list-row" style={{ display: "block", paddingTop: 14, paddingBottom: 14 }}>
          <Segmented
            label="OCR 后端"
            value={form.ocr_backend}
            onChange={(key) => set("ocr_backend", key)}
            options={[
              ["paddleocr", "PaddleOCR（本地）"],
              ["api", "视觉大模型 API"],
            ]}
          />
        </div>

        {form.ocr_backend === "api" ? (
          <div className="list-row" style={{ display: "block" }}>
            <div className="grid-2">
              <Field label="接口地址">
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={form.ocr_api_url}
                    onChange={(event) => set("ocr_api_url", event.target.value)}
                    placeholder="https://..."
                  />
                )}
              </Field>
              <Field label="模型名">
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={form.ocr_api_model}
                    onChange={(event) => set("ocr_api_model", event.target.value)}
                    placeholder="glm-4v-flash"
                  />
                )}
              </Field>
              <Field label="API Key" hint={keyHint(Boolean(data.ocr?.api?.api_key))}>
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    type="password"
                    value={form.ocr_api_key}
                    onChange={(event) => set("ocr_api_key", event.target.value)}
                    autoComplete="off"
                  />
                )}
              </Field>
            </div>
          </div>
        ) : null}

        {check ? (
          <div className="list-row" style={{ display: "block" }}>
            {check.ok ? (
              <>
                <div className="row-wrap" style={{ marginBottom: 8 }}>
                  <Badge tone={check.average >= 0.85 ? "ok" : "warn"}>
                    平均相似度 {(check.average * 100).toFixed(1)}%
                  </Badge>
                  <span className="t-footnote c-secondary">阈值 0.85，忽略空格差异</span>
                </div>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>期望</th>
                        <th>识别</th>
                        <th style={{ textAlign: "right" }}>相似度</th>
                      </tr>
                    </thead>
                    <tbody>
                      {check.cases.map((item, index) => (
                        <tr key={index}>
                          <td className="t-mono">{item.expected}</td>
                          <td className="t-mono">{item.actual || "—"}</td>
                          <td className="tnum" style={{ textAlign: "right" }}>
                            {item.similarity.toFixed(3)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <Banner tone="danger" icon="alert">
                {check.error || "自检失败"}
              </Banner>
            )}
          </div>
        ) : null}
      </Group>

      <Group title="向量库" footer="每门课独立目录；cloud 模式连 Chroma Server。">
        <div className="list-row" style={{ display: "block" }}>
          <div className="grid-2">
            <Field label="类型">
              {(id) => (
                <select
                  id={id}
                  className="select"
                  value={form.vs_backend}
                  onChange={(event) => set("vs_backend", event.target.value)}
                >
                  <option value="chroma">Chroma</option>
                </select>
              )}
            </Field>
            <Field label="部署模式">
              {(id) => (
                <select
                  id={id}
                  className="select"
                  value={form.vs_mode}
                  onChange={(event) => set("vs_mode", event.target.value)}
                >
                  <option value="local">本地目录</option>
                  <option value="cloud">Chroma Server</option>
                </select>
              )}
            </Field>
            {form.vs_mode === "cloud" ? (
              <>
                <Field label="Host">
                  {(id) => (
                    <input
                      id={id}
                      className="input"
                      value={form.vs_host}
                      onChange={(event) => set("vs_host", event.target.value)}
                    />
                  )}
                </Field>
                <Field label="Port">
                  {(id) => (
                    <input
                      id={id}
                      className="input tnum"
                      type="number"
                      value={form.vs_port}
                      onChange={(event) => set("vs_port", event.target.value)}
                    />
                  )}
                </Field>
                <Field label="Token" hint={keyHint(Boolean(data.vectorStore?.chroma?.token))}>
                  {(id) => (
                    <input
                      id={id}
                      className="input"
                      type="password"
                      value={form.vs_token}
                      onChange={(event) => set("vs_token", event.target.value)}
                      autoComplete="off"
                    />
                  )}
                </Field>
                <div className="field" style={{ justifyContent: "flex-end" }}>
                  <span className="field-label">传输</span>
                  <div className="spread">
                    <span className="t-body">使用 SSL</span>
                    <Switch
                      checked={form.vs_ssl}
                      onChange={(checked) => set("vs_ssl", checked)}
                      aria-label="使用 SSL"
                    />
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </Group>

      <Group title="嵌入模型" footer="决定相似度与 RAG 检索质量；切换后需要重新评分才能重建维度库。">
        <div className="list-row" style={{ display: "block" }}>
          <div className="grid-2">
            <Field label="后端">
              {(id) => (
                <select
                  id={id}
                  className="select"
                  value={form.emb_backend}
                  onChange={(event) => set("emb_backend", event.target.value)}
                >
                  <option value="default">内置离线</option>
                  <option value="openai">OpenAI 兼容 /embeddings</option>
                </select>
              )}
            </Field>
            {form.emb_backend === "openai" ? (
              <>
                <Field label="Base URL">
                  {(id) => (
                    <input
                      id={id}
                      className="input"
                      value={form.emb_url}
                      onChange={(event) => set("emb_url", event.target.value)}
                    />
                  )}
                </Field>
                <Field label="模型名">
                  {(id) => (
                    <input
                      id={id}
                      className="input"
                      value={form.emb_model}
                      onChange={(event) => set("emb_model", event.target.value)}
                      placeholder="text-embedding-3-small"
                    />
                  )}
                </Field>
                <Field
                  label="API Key"
                  hint={keyHint(Boolean(data.vectorStore?.embedding?.openai?.api_key))}
                >
                  {(id) => (
                    <input
                      id={id}
                      className="input"
                      type="password"
                      value={form.emb_key}
                      onChange={(event) => set("emb_key", event.target.value)}
                      autoComplete="off"
                    />
                  )}
                </Field>
              </>
            ) : null}
          </div>
        </div>
      </Group>

      <Group
        title="评分并发"
        footer="同时评分的报告份数，1-8，默认 3。供应商限流（429）或本地 Ollama 显存不足时调低；保存后下一轮评分生效。"
      >
        <div className="list-row" style={{ display: "block", paddingTop: 14, paddingBottom: 14 }}>
          <div className="grid-2">
            <Field label="并行评分份数">
              {(id) => (
                <input
                  id={id}
                  className="input tnum"
                  type="number"
                  min={1}
                  max={8}
                  value={form.grading_workers}
                  onChange={(event) => set("grading_workers", event.target.value)}
                />
              )}
            </Field>
          </div>
        </div>
      </Group>

      <Banner icon="info">
        保存后无需重启进程。若首屏生成细则报错，先确认 Base URL、模型名与 API Key（填环境变量名时确认该变量已配置）。
      </Banner>
    </>
  );
}
