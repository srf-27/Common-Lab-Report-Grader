import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, errorText, getJSON, postEmpty, postForm, postJSON } from "../lib/api";
import { LEVELS, LEVEL_LABEL } from "../lib/format";
import { useData, usePoll } from "../lib/hooks";
import { toast } from "../lib/toast";
import {
  AutoTextarea,
  Badge,
  Banner,
  Button,
  Disclosure,
  Dropzone,
  Empty,
  Field,
  Group,
  IconButton,
  PageHead,
  Progress,
  Sheet,
  Spinner,
  Switch,
} from "../ui";

const emptyCriterion = () => ({
  name: "",
  weight: 0,
  mechanical: false,
  doc_ref: "",
  levels: { A: "", B: "", C: "", D: "", E: "" },
  rules: null,
});

export default function Rubric() {
  const { data, error, loading, load } = useData("/api/rubric");
  const [draft, setDraft] = useState([]);
  const [file, setFile] = useState(null);
  const [task, setTask] = useState(null);
  const [polling, setPolling] = useState(false);
  const [busy, setBusy] = useState(false);
  const [genIndex, setGenIndex] = useState(-1);
  const [warnings, setWarnings] = useState(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    getJSON("/task_status")
      .then((next) => {
        if (next?.status === "running") {
          setTask(next);
          setPolling(true);
        }
      })
      .catch(() => {});
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!data) return;
    setDraft(
      (data.rubric?.criteria || []).map((item) => ({ ...item, levels: { ...(item.levels || {}) } }))
    );
  }, [data]);

  const tick = useCallback(async () => {
    try {
      const next = await getJSON("/task_status");
      if (!mounted.current) return;
      setTask(next);
      if (next.status !== "running") {
        setPolling(false);
        if (next.status === "done") {
          toast(next.detail || "评分细则已生成", "ok");
          load();
        } else if (next.status === "error") {
          toast(next.error || "生成失败", "danger");
        }
      }
    } catch (err) {
      setPolling(false);
      toast(errorText(err), "danger");
    }
  }, [load]);

  usePoll(tick, 1200, polling);

  const total = useMemo(
    () => draft.reduce((sum, item) => sum + (Number(item.weight) || 0), 0),
    [draft]
  );
  const dirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(data?.rubric?.criteria || []),
    [data, draft]
  );

  const patch = (index, changes) =>
    setDraft((list) => list.map((item, i) => (i === index ? { ...item, ...changes } : item)));

  const patchLevel = (index, level, value) =>
    setDraft((list) =>
      list.map((item, i) => (i === index ? { ...item, levels: { ...item.levels, [level]: value } } : item))
    );

  const generate = async () => {
    if (!file) return toast("请先选择评分标准文件", "danger");
    setBusy(true);
    try {
      await postForm("/upload_criteria", { criteria_file: file });
      await postForm("/process_criteria", {});
      const next = await getJSON("/task_status");
      if (next?.status !== "running") {
        toast("没能开始生成：文件可能没有可读文本", "danger");
        return;
      }
      setTask(next);
      setPolling(true);
      setFile(null);
      toast("已开始生成细则，完成后会自动刷新", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  const save = async (force = false) => {
    if (!draft.length) return toast("至少保留一个评分维度", "danger");
    if (draft.some((item) => !String(item.name).trim())) return toast("存在未命名维度", "danger");
    setBusy(true);
    try {
      await postJSON("/rubric_table_save", {
        criteria: draft.map((item) => ({
          name: String(item.name).trim(),
          weight: Number(item.weight) || 0,
          mechanical: Boolean(item.mechanical),
          doc_ref: item.doc_ref || "",
          levels: item.levels,
          rules: item.rules || null,
        })),
        force,
      });
      setWarnings(null);
      await load();
      toast("评分细则已保存", "ok");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && err.data?.warnings) {
        setWarnings(err.data.warnings);
      } else {
        toast(errorText(err), "danger");
      }
    } finally {
      setBusy(false);
    }
  };

  const fillCell = async (index) => {
    const item = draft[index];
    const fields = [];
    if (!Number(item.weight)) fields.push("weight");
    if (!String(item.doc_ref || "").trim()) fields.push("doc_ref");
    LEVELS.forEach((level) => {
      if (!String(item.levels?.[level] || "").trim()) fields.push(level);
    });
    if (!fields.length) return toast("该维度的字段已经完整");
    setGenIndex(index);
    try {
      const filled = await postJSON("/rubric_gen_cell", {
        name: item.name,
        fields,
        context: { weight: item.weight, doc_ref: item.doc_ref },
      });
      const changes = {};
      if (filled.weight !== undefined) changes.weight = filled.weight;
      if (filled.doc_ref !== undefined) changes.doc_ref = filled.doc_ref;
      // 后端按 CELL_PROMPT 返回 {"levels": {"A": ...}}，兼容旧的扁平结构
      const incoming = filled.levels && typeof filled.levels === "object" ? filled.levels : filled;
      const levels = { ...item.levels };
      LEVELS.forEach((level) => {
        if (incoming[level]) levels[level] = incoming[level];
      });
      changes.levels = levels;
      patch(index, changes);
      toast("已补全该维度，记得保存", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setGenIndex(-1);
    }
  };

  const progress = task?.progress || 0;

  return (
    <>
      <PageHead
        title="评分细则"
        sub={`${data?.criteria?.length || 0} 个维度 · 权重合计 ${Math.round(total * 10) / 10}% · 标准原文 ${
          data?.docChars || 0
        } 字`}
        actions={
          <>
            {data?.hasMarkdown ? (
              <a className="btn" href="/download/rubrics/rubric_latest.md">
                Markdown
              </a>
            ) : null}
            <Button
              variant="filled"
              icon="check"
              disabled={!dirty || busy || !draft.length}
              loading={busy}
              onClick={() => save()}
            >
              保存
            </Button>
          </>
        }
      />

      {error ? (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="danger" icon="alert">
            {error}
          </Banner>
        </div>
      ) : null}

      {task ? (
        <div style={{ marginBottom: 18 }}>
          <Group
            title={task.status === "running" ? "正在生成评分细则" : "上次生成"}
            note={task.stage || ""}
            actions={
              task.status === "running" ? (
                <Button size="sm" onClick={() => postEmpty("/task_cancel").then(() => toast("已请求取消"))}>
                  取消
                </Button>
              ) : (
                <IconButton icon="x" label="收起" onClick={() => setTask(null)} />
              )
            }
          >
            <div className="list-row" style={{ display: "block" }}>
              <Progress value={progress} tone={task.status === "error" ? "danger" : undefined} />
              <div className="spread" style={{ marginTop: 8 }}>
                <span className="row-sub" style={{ whiteSpace: "normal" }}>
                  {task.detail || task.stage || "准备中"}
                </span>
                <span className="t-footnote tnum c-secondary">{progress}%</span>
              </div>
            </div>
          </Group>
        </div>
      ) : null}

      {data?.warnings?.length ? (
        <div style={{ marginBottom: 18 }}>
          <Banner tone="warn" icon="alert">
            {data.warnings.map((item, index) => (
              <div key={index}>
                <strong>{item.criterion}</strong>：{item.message}
              </div>
            ))}
          </Banner>
        </div>
      ) : null}

      <Group
        title="评分标准原文"
        note=".docx / .pdf / .txt"
        footer="生成会调用一次模型，通常 1–3 分钟；重新生成会覆盖现有维度。"
      >
        <Dropzone
          accept=".docx,.pdf,.txt"
          title={file ? file.name : "选择评分标准"}
          hint="纯扫描件无法提取文字，请先 OCR 或换可复制的文件"
          onFiles={(files) => setFile(files[0])}
          disabled={polling}
        />
        <div className="list-row" style={{ gap: 8 }}>
          <Button
            variant="filled"
            icon="play"
            disabled={!file || busy || polling}
            loading={busy && !polling}
            onClick={generate}
          >
            上传并生成细则
          </Button>
          {file ? (
            <Button variant="plain" onClick={() => setFile(null)}>
              清除
            </Button>
          ) : null}
          <span className="row-sub" style={{ marginLeft: "auto" }}>
            {data?.hasUpload ? "已上传过标准" : "尚未上传"}
          </span>
        </div>
      </Group>

      <Group
        title="评分维度"
        note={`${draft.length} 个 · 权重合计 ${Math.round(total * 10) / 10}%`}
        actions={
          <Button size="sm" icon="plus" onClick={() => setDraft((list) => [...list, emptyCriterion()])}>
            新增
          </Button>
        }
      >
        {loading && !draft.length ? (
          <Spinner label="读取细则…" />
        ) : draft.length ? (
          draft.map((item, index) => (
            <Disclosure
              key={index}
              defaultOpen={!String(item.name).trim()}
              summary={
                <span className="row" style={{ minWidth: 0, gap: 8 }}>
                  <span className="row-title">
                    {String(item.name).trim() || "未命名维度"}
                  </span>
                  <span className="row-sub" style={{ margin: 0 }}>
                    {Number(item.weight) || 0}%
                  </span>
                  {item.mechanical ? <Badge tone="accent">机械</Badge> : null}
                </span>
              }
              meta={
                <>
                  <span className="row" style={{ gap: 2 }} aria-hidden="true">
                    {LEVELS.map((level) => (
                      <span
                        key={level}
                        className={`level level-${item.levels?.[level] ? level : "none"}`}
                        title={`${level} ${LEVEL_LABEL[level]}：${item.levels?.[level] || "未填写"}`}
                      >
                        {level}
                      </span>
                    ))}
                  </span>
                  <Button
                    size="sm"
                    icon="refresh"
                    loading={genIndex === index}
                    disabled={genIndex >= 0}
                    onClick={() => fillCell(index)}
                  >
                    补全
                  </Button>
                  <IconButton
                    icon="trash"
                    label="删除维度"
                    onClick={() => setDraft((list) => list.filter((_, i) => i !== index))}
                  />
                </>
              }
            >
              <div className="grid-2" style={{ marginBottom: 12 }}>
                <Field label="维度名称">
                  {(id) => (
                    <input
                      id={id}
                      className="input"
                      value={item.name}
                      onChange={(event) => patch(index, { name: event.target.value })}
                    />
                  )}
                </Field>
                <Field label="权重 %" hint="保存时按比例归一到 100%">
                  {(id) => (
                    <input
                      id={id}
                      className="input tnum"
                      type="number"
                      min="0"
                      step="0.5"
                      value={item.weight}
                      onChange={(event) => patch(index, { weight: event.target.value })}
                    />
                  )}
                </Field>
              </div>
              <div className="grid-2" style={{ marginBottom: 12 }}>
                <Field label="标准文档位置" hint="指向标准原文的章节或条目">
                  {(id) => (
                    <input
                      id={id}
                      className="input"
                      value={item.doc_ref || ""}
                      onChange={(event) => patch(index, { doc_ref: event.target.value })}
                    />
                  )}
                </Field>
                <div className="field" style={{ justifyContent: "flex-end" }}>
                  <span className="field-label">判决方式</span>
                  <div className="spread">
                    <span className="t-body">可程序化判定</span>
                    <Switch
                      checked={Boolean(item.mechanical)}
                      onChange={(checked) => patch(index, { mechanical: checked })}
                      aria-label="可程序化判定"
                    />
                  </div>
                </div>
              </div>
              <div className="stack" style={{ gap: 10 }}>
                {LEVELS.map((level) => (
                  <Field key={level} label={`${level} · ${LEVEL_LABEL[level]}`}>
                    {(id) => (
                      <AutoTextarea
                        id={id}
                        value={item.levels?.[level] || ""}
                        onChange={(event) => patchLevel(index, level, event.target.value)}
                      />
                    )}
                  </Field>
                ))}
              </div>
            </Disclosure>
          ))
        ) : (
          <div style={{ padding: 16 }}>
            <Empty
              icon="rubric"
              title="还没有评分维度"
              text="上传评分标准并生成，或直接手动新增维度。"
              action={
                <Button icon="plus" onClick={() => setDraft([emptyCriterion()])}>
                  手动新增维度
                </Button>
              }
            />
          </div>
        )}
      </Group>

      {dirty ? (
        <div className="action-bar">
          <span className="t-subhead grow">有未保存的修改</span>
          <Button
            onClick={() =>
              setDraft(
                (data?.rubric?.criteria || []).map((item) => ({
                  ...item,
                  levels: { ...(item.levels || {}) },
                }))
              )
            }
          >
            放弃
          </Button>
          <Button variant="filled" loading={busy} onClick={() => save()}>
            保存
          </Button>
        </div>
      ) : null}

      <Sheet
        open={Boolean(warnings)}
        title="细则校验未通过"
        text="这些问题会让判级边界变模糊，确认后仍可强行保存。"
        onClose={() => setWarnings(null)}
        footer={
          <>
            <Button onClick={() => setWarnings(null)}>返回修改</Button>
            <Button variant="filled" loading={busy} onClick={() => save(true)}>
              仍然保存
            </Button>
          </>
        }
      >
        <ul style={{ margin: 0, paddingLeft: 18, color: "var(--label-2)", lineHeight: 1.5 }}>
          {(warnings || []).map((item, index) => (
            <li key={index} style={{ marginBottom: 6 }}>
              <strong style={{ color: "var(--label)" }}>{item.criterion}</strong>：{item.message}
            </li>
          ))}
        </ul>
      </Sheet>
    </>
  );
}
