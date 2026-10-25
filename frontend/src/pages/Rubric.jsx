import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, errorText, getJSON, postEmpty, postForm, postFormJSON, postJSON } from "../lib/api";
import { LEVELS, LEVEL_LABEL } from "../lib/format";
import { Prose } from "../lib/markdown";
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
  LevelPicker,
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

const metric = (value) =>
  typeof value === "number" && !Number.isNaN(value) ? value.toFixed(3) : "—";

const missingFields = (item) => {
  const fields = [];
  if (!Number(item.weight)) fields.push("weight");
  if (!String(item.doc_ref || "").trim()) fields.push("doc_ref");
  LEVELS.forEach((level) => {
    if (!String(item.levels?.[level] || "").trim()) fields.push(level);
  });
  return fields;
};

export default function Rubric() {
  const { data, error, loading, load } = useData("/api/rubric");
  const { data: pilotData, load: loadPilot } = useData("/api/pilot");
  const [draft, setDraft] = useState([]);
  const [file, setFile] = useState(null);
  const [flowFile, setFlowFile] = useState(null);
  const [mode, setMode] = useState("single");
  const [externalFile, setExternalFile] = useState(null);
  const [externalBusy, setExternalBusy] = useState(false);
  const [pilotFiles, setPilotFiles] = useState([]);
  const [pilotLevels, setPilotLevels] = useState({});
  const [pilotBusy, setPilotBusy] = useState(false);
  const [pilotTask, setPilotTask] = useState(null);
  const [pilotPolling, setPilotPolling] = useState(false);
  const [reader, setReader] = useState(null);
  const [readerText, setReaderText] = useState("");
  const [readerBusy, setReaderBusy] = useState(false);
  const [task, setTask] = useState(null);
  const [polling, setPolling] = useState(false);
  const [busy, setBusy] = useState(false);
  const [genIndex, setGenIndex] = useState(-1);
  const [warnings, setWarnings] = useState(null);
  const mounted = useRef(true);
  const modeInit = useRef(false);

  useEffect(() => {
    mounted.current = true;
    getJSON("/task_status")
      .then((next) => {
        if (next?.kind === "criteria" && next.status === "running") {
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
    if (!modeInit.current) {
      modeInit.current = true;
      setMode(data.mode === "pair" ? "pair" : "single");
    }
  }, [data]);

  useEffect(() => {
    if (!pilotData) return;
    const next = {};
    (pilotData.reports || []).forEach((report) => {
      next[report.filename] = { ...(report.teacher || {}) };
    });
    setPilotLevels(next);
  }, [pilotData]);

  const pilotTick = useCallback(async () => {
    try {
      const next = await getJSON("/task_status");
      if (!mounted.current || next?.kind !== "pilot") return;
      setPilotTask(next);
      if (next.status !== "running") {
        setPilotPolling(false);
        if (next.status === "done") {
          toast("样本已评完，请填写你的等级", "ok");
          loadPilot();
        } else if (next.status === "error") {
          toast(next.error || "样本评分失败", "danger");
        }
      }
    } catch (err) {
      setPilotPolling(false);
      toast(errorText(err), "danger");
    }
  }, [loadPilot]);

  usePoll(pilotTick, 1200, pilotPolling);

  const uploadPilot = async () => {
    if (!pilotFiles.length) return toast("请先选择测试报告", "danger");
    setPilotBusy(true);
    try {
      await postForm("/pilot/upload", { pilot_files: pilotFiles });
      setPilotFiles([]);
      await loadPilot();
      toast("测试报告已解析", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setPilotBusy(false);
    }
  };

  const runPilot = async () => {
    setPilotBusy(true);
    try {
      await postJSON("/pilot/run", {});
      const next = await getJSON("/task_status");
      if (next?.kind !== "pilot" || next.status !== "running") {
        toast("没能开始评分", "danger");
        return;
      }
      setPilotTask(next);
      setPilotPolling(true);
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setPilotBusy(false);
    }
  };

  const savePilotLevels = async () => {
    setPilotBusy(true);
    try {
      await postJSON("/pilot/teacher", { levels: pilotLevels });
      await loadPilot();
      toast("你的等级已保存", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setPilotBusy(false);
    }
  };

  const confirmPilot = async () => {
    setPilotBusy(true);
    try {
      await postJSON("/pilot/confirm", {});
      await loadPilot();
      toast("细则已确认，可以进入上传报告", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setPilotBusy(false);
    }
  };

  const openPilotText = async (report) => {
    setReader(report);
    setReaderBusy(true);
    setReaderText("");
    try {
      const payload = await getJSON(`/pilot/text/${encodeURIComponent(report.filename)}`);
      setReaderText(payload.text || "");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setReaderBusy(false);
    }
  };

  const tick = useCallback(async () => {
    try {
      const next = await getJSON("/task_status");
      if (!mounted.current) return;
      if (next?.kind !== "criteria") return;
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
  const excludedDims = useMemo(() => draft.filter((item) => item.excluded), [draft]);
  const excludableDims = useMemo(
    () => draft.filter((item) => item.can_exclude || item.excluded),
    [draft]
  );
  const allExcluded =
    excludableDims.length > 0 && excludableDims.every((item) => item.excluded);
  const externalDims = data?.external?.dimensions || {};

  const patch = (index, changes) =>
    setDraft((list) => list.map((item, i) => (i === index ? { ...item, ...changes } : item)));

  const toggleExcludable = (checked) =>
    setDraft((list) =>
      list.map((item) =>
        item.can_exclude || item.excluded ? { ...item, excluded: checked } : item
      )
    );

  const patchLevel = (index, level, value) =>
    setDraft((list) =>
      list.map((item, i) => (i === index ? { ...item, levels: { ...item.levels, [level]: value } } : item))
    );

  const generate = async () => {
    if (!file) return toast(mode === "pair" ? "请先选择课程大纲" : "请先选择评分标准文件", "danger");
    if (mode === "pair" && !flowFile) return toast("请再选择实验流程或实验模板", "danger");
    setBusy(true);
    try {
      const fields = { criteria_file: file };
      if (mode === "pair") fields.experiment_file = flowFile;
      await postForm("/upload_criteria", fields);
      await postForm("/process_criteria", {});
      const next = await getJSON("/task_status");
      if (next?.kind !== "criteria" || next.status !== "running") {
        toast("没能开始生成：文件可能没有可读文本", "danger");
        return;
      }
      setTask(next);
      setPolling(true);
      setFile(null);
      setFlowFile(null);
      toast(mode === "pair" ? "已开始生成，完成后会自动刷新" : "已开始生成细则，完成后会自动刷新", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  const uploadExternal = async () => {
    if (!externalFile) return;
    if (dirty) return toast("请先保存细则，再上传成绩单", "danger");
    setExternalBusy(true);
    try {
      const result = await postFormJSON("/rubric_external_upload", { external_file: externalFile });
      const dims = Object.keys(result.dimensions || {}).length;
      toast(`已合并 ${dims} 个维度、${result.applied || 0} 条分数`, "ok");
      setExternalFile(null);
      await load();
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setExternalBusy(false);
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
          excluded: Boolean(item.excluded),
          non_report: Boolean(item.non_report),
          doc_ref: item.doc_ref || "",
          levels: item.levels,
          rules: item.rules || null,
        })),
        force,
      });
      setWarnings(null);
      await load();
      loadPilot();
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
    const fields = missingFields(item);
    if (!fields.length) return toast("该维度的字段已经完整");
    setGenIndex(index);
    try {
      const requested = new Set(fields);
      const filled = await postJSON("/rubric_gen_cell", {
        name: item.name,
        fields,
        context: {
          weight: item.weight,
          doc_ref: item.doc_ref,
          levels: item.levels || {},
          non_report: Boolean(item.non_report),
          excluded: Boolean(item.excluded),
        },
      });
      const changes = {};
      if (requested.has("weight") && filled.weight !== undefined) changes.weight = filled.weight;
      if (requested.has("doc_ref") && filled.doc_ref !== undefined) changes.doc_ref = filled.doc_ref;
      // 后端按 CELL_PROMPT 返回 {"levels": {"A": ...}}，兼容旧的扁平结构
      const incoming = filled.levels && typeof filled.levels === "object" ? filled.levels : filled;
      const levels = { ...item.levels };
      LEVELS.forEach((level) => {
        if (requested.has(level) && String(incoming[level] || "").trim()) {
          levels[level] = incoming[level];
        }
      });
      changes.levels = levels;
      patch(index, changes);
      const missing = fields.filter((field) => {
        if (field === "weight") return !Number(changes.weight ?? item.weight);
        if (field === "doc_ref") return !String(changes.doc_ref ?? item.doc_ref).trim();
        return !String(levels[field] || "").trim();
      });
      if (missing.length) {
        toast(`模型未补全：${missing.join("、")}`, "danger");
      } else {
        toast("已补全该维度，记得保存", "ok");
      }
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
        } 字${data?.experimentChars ? ` · 实验流程 ${data.experimentChars} 字` : ""}`}
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
              {task.mode === "stage" ? (
                /* 单次长 LLM 调用没有可如实量化的百分比：展示阶段 + 已运行时长 */
                <>
                  <div className="spread" style={{ gap: 10 }}>
                    <span className="row-sub" style={{ whiteSpace: "normal" }}>
                      {task.status === "running" ? (
                        <Spinner size="sm" label={task.stage || "处理中"} />
                      ) : (
                        task.stage || "结束"
                      )}
                    </span>
                    {task.elapsed != null ? (
                      <span className="t-footnote tnum c-secondary">已运行 {Math.round(task.elapsed)}s</span>
                    ) : null}
                  </div>
                  {task.detail ? (
                    <div className="t-footnote c-secondary" style={{ marginTop: 6, whiteSpace: "normal" }}>
                      {task.detail}
                    </div>
                  ) : null}
                  {task.status === "error" ? (
                    <div style={{ marginTop: 8 }}>
                      <Banner tone="danger" icon="alert">{task.error || "生成失败"}</Banner>
                    </div>
                  ) : null}
                </>
              ) : (
                <>
                  <Progress value={progress} tone={task.status === "error" ? "danger" : undefined} />
                  <div className="spread" style={{ marginTop: 8 }}>
                    <span className="row-sub" style={{ whiteSpace: "normal" }}>
                      {task.detail || task.stage || "准备中"}
                    </span>
                    <span className="t-footnote tnum c-secondary">{progress}%</span>
                  </div>
                </>
              )}
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
        note={mode === "pair" ? "课程大纲 + 实验流程" : ".docx / .pdf / .txt"}
        footer="单份标准：一份文件里写明维度与权重。双文件：大纲给课程目标与分值，实验流程给本次实验的对象和数据，判据会落到具体步骤上。"
      >
        <div className="list-row" style={{ gap: 8, flexWrap: "wrap" }}>
          <Button
            size="sm"
            variant={mode === "single" ? "filled" : "tinted"}
            onClick={() => setMode("single")}
          >
            单份标准文档
          </Button>
          <Button
            size="sm"
            variant={mode === "pair" ? "filled" : "tinted"}
            onClick={() => setMode("pair")}
          >
            课程大纲 + 实验流程
          </Button>
          <span className="row-sub" style={{ marginLeft: "auto" }}>
            {mode === "pair" ? "大纲定权重，实验材料定判据" : "一份文件包含全部评分要求"}
          </span>
        </div>
        {mode === "single" ? (
          <Dropzone
            accept=".docx,.pdf,.txt"
            selected={file ? [file] : []}
            title="拖拽评分标准到这里"
            hint="支持 .docx / .pdf / .txt；纯扫描件需先 OCR"
            onFiles={(files) => setFile(files[0])}
            disabled={polling}
          />
        ) : (
          <>
            <Dropzone
              accept=".docx,.pdf,.txt"
              selected={file ? [file] : []}
              title="拖拽课程大纲到这里"
              hint="课程目标、考核方式、报告要求、分值构成"
              onFiles={(files) => setFile(files[0])}
              disabled={polling}
            />
            <Dropzone
              accept=".docx,.pdf,.txt"
              selected={flowFile ? [flowFile] : []}
              title="拖拽实验流程 / 实验模板到这里"
              hint="本次实验的目的、原理、步骤、数据表与产物"
              onFiles={(files) => setFlowFile(files[0])}
              disabled={polling}
            />
          </>
        )}
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
          {file || flowFile ? (
            <Button
              variant="plain"
              onClick={() => {
                setFile(null);
                setFlowFile(null);
              }}
            >
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
        footer="报告无关的维度（预习、课堂等）生成时默认停用，避免摊薄报告证据；取消勾选即可计入。停用后权重保留、导出留空列，可用课外成绩单补分。"
        actions={
          <>
            <label
              className="check check-inline"
              data-disabled={excludableDims.length ? undefined : "true"}
              title={
                excludableDims.length
                  ? "把与报告无关的维度停用：仍占总分，但不参与报告评分"
                  : "当前所有维度都能从报告中找到证据，不需要停用"
              }
            >
              <input
                type="checkbox"
                checked={allExcluded}
                disabled={!excludableDims.length}
                onChange={(event) => toggleExcludable(event.target.checked)}
              />
              <span className="check-label">删去不相干维度（保留分值）</span>
            </label>
            <Button size="sm" icon="plus" onClick={() => setDraft((list) => [...list, emptyCriterion()])}>
              新增
            </Button>
          </>
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
                  {item.non_report && !item.excluded ? (
                    <Badge tone="warn">建议停用</Badge>
                  ) : null}
                  {item.edited ? <Badge tone="warn">已改</Badge> : null}
                  {item.excluded ? (
                    <Badge tone={item.external_count ? "ok" : "warn"}>
                      {item.external_count ? "已打分" : "停用"}
                    </Badge>
                  ) : null}
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
                    disabled={genIndex >= 0 || missingFields(item).length === 0}
                    title={
                      missingFields(item).length
                        ? "补全空着的字段"
                        : "所有字段已完整，不需要补全"
                    }
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

      {draft.length ? (
      <Group
        title="第 2 步 · 样本校准"
        note={
          pilotData?.reports?.length
            ? `${pilotData.reports.length}/5 份`
            : "最多 5 份"
        }
        footer="模型与你先各评一次，看一致性。维度可以继续改，改完需要重新确认；确认之后才允许开始正式评分。"
      >
        <div className="list-row" style={{ display: "block" }}>
          <div className="row" style={{ gap: 8 }}>
            <Badge
              tone={pilotData?.confirmed ? "ok" : pilotData?.needsConfirm ? "warn" : ""}
            >
              {pilotData?.confirmed
                ? "已确认"
                : pilotData?.needsConfirm
                  ? "细则已改，需重新确认"
                  : "待校准"}
            </Badge>
            <span className="row-sub" style={{ margin: 0 }}>
              {pilotData?.confirmed
                ? "可以进入上传报告"
                : "未确认前不能开始正式评分"}
            </span>
          </div>
        </div>
        <Dropzone
          multiple
          accept=".pdf,.docx,.doc,.md"
          selected={pilotFiles}
          title="拖拽测试报告到这里"
          hint="1–5 份；只用于校准，不计入正式成绩"
          onFiles={setPilotFiles}
          disabled={pilotBusy || pilotPolling}
        />
        <div className="list-row" style={{ gap: 8, flexWrap: "wrap" }}>
          <Button
            icon="upload"
            disabled={!pilotFiles.length || pilotBusy || pilotPolling}
            onClick={uploadPilot}
          >
            上传并解析
          </Button>
          <Button
            icon="play"
            disabled={!pilotData?.reports?.length || pilotBusy || pilotPolling}
            loading={pilotPolling}
            onClick={runPilot}
          >
            模型评分
          </Button>
          <span className="row-sub" style={{ marginLeft: "auto" }}>
            {pilotTask?.status === "running"
              ? `${pilotTask.progress || 0}% · ${pilotTask.detail || ""}`
              : ""}
          </span>
        </div>
        {(pilotData?.reports || []).map((report) => {
          const assigned = new Set(Object.keys(report.assignments || {}));
          const rest = (report.chunks || []).filter((_, index) => !assigned.has(`p${index}`));
          return (
            <Disclosure
              key={report.filename}
              summary={
                <span className="row" style={{ minWidth: 0, gap: 8 }}>
                  <span className="row-title truncate">{report.filename}</span>
                  <Badge tone={report.status === "graded" ? "ok" : ""}>
                    {report.status === "graded" ? "模型已评" : report.status || "待评"}
                  </Badge>
                </span>
              }
              meta={
                <span className="row" style={{ gap: 8 }}>
                  <span className="row-sub" style={{ margin: 0 }}>
                    {Object.keys(report.teacher || {}).length}/
                    {draft.filter((i) => !i.excluded).length} 已填
                  </span>
                  <Button size="sm" icon="external" onClick={() => openPilotText(report)}>
                    原文
                  </Button>
                </span>
              }
            >
              <div className="stack" style={{ gap: 8 }}>
                {draft
                  .filter((item) => !item.excluded)
                  .map((item) => {
                    const paragraphs = Object.entries(report.assignments || {})
                      .filter(([, entry]) => (entry || {}).criterion === item.name)
                      .map(([id]) => report.chunks?.[Number(id.slice(1))])
                      .filter(Boolean);
                    return (
                      <Disclosure
                        key={item.name}
                        summary={
                          <span className="row" style={{ minWidth: 0, gap: 8 }}>
                            <span className="t-footnote truncate">{item.name}</span>
                            <Badge outline>AI {report.ai?.[item.name] || "—"}</Badge>
                          </span>
                        }
                        meta={
                          <span className="row" style={{ gap: 8 }}>
                            <span className="row-sub" style={{ margin: 0 }}>
                              {paragraphs.length} 段
                            </span>
                            <LevelPicker
                              allowEmpty
                              value={pilotLevels[report.filename]?.[item.name] || ""}
                              onChange={(level) =>
                                setPilotLevels((prev) => ({
                                  ...prev,
                                  [report.filename]: {
                                    ...(prev[report.filename] || {}),
                                    [item.name]: level,
                                  },
                                }))
                              }
                            />
                          </span>
                        }
                      >
                        {paragraphs.length ? (
                          paragraphs.map((chunk, chunkIndex) => (
                            <div key={chunkIndex} className="quote" style={{ marginBottom: 6 }}>
                              <Prose text={chunk} />
                            </div>
                          ))
                        ) : (
                          <span className="row-sub">未挂载段落</span>
                        )}
                      </Disclosure>
                    );
                  })}
                {rest.length ? (
                  <Disclosure
                    summary={<span className="t-footnote">未挂载内容</span>}
                    meta={
                      <span className="row-sub" style={{ margin: 0 }}>
                        {rest.length} 段
                      </span>
                    }
                  >
                    {rest.map((chunk, chunkIndex) => (
                      <div key={chunkIndex} className="quote" style={{ marginBottom: 6 }}>
                        <Prose text={chunk} />
                      </div>
                    ))}
                  </Disclosure>
                ) : null}
              </div>
            </Disclosure>
          );
        })}
        {pilotData?.agreement?.n ? (
          <div className="list-row" style={{ justifyContent: "space-between", gap: 12 }}>
            <span className="row-sub" style={{ margin: 0 }}>
              一致性 · n={pilotData.agreement.n}
            </span>
            <span className="row" style={{ gap: 12 }}>
              <span className="t-footnote tnum">
                κ {metric(pilotData.agreement.cohen_kappa)}
              </span>
              <span className="t-footnote tnum">
                加权 κ {metric(pilotData.agreement.weighted_kappa)}
              </span>
              <span className="t-footnote tnum">
                α {metric(pilotData.agreement.krippendorff_alpha)}
              </span>
            </span>
          </div>
        ) : null}
        <div className="list-row" style={{ gap: 8, flexWrap: "wrap" }}>
          <Button
            onClick={savePilotLevels}
            disabled={!pilotData?.reports?.length || pilotBusy}
          >
            保存我的等级
          </Button>
          <Button
            variant="filled"
            icon="check"
            onClick={confirmPilot}
            disabled={pilotBusy || pilotData?.confirmed}
            loading={pilotBusy}
          >
            {pilotData?.confirmed ? "已确认" : "确认细则，进入下一步"}
          </Button>
          {pilotData?.confirmed ? (
            <span className="row-sub">可以直接上传报告了</span>
          ) : (
            <span className="row-sub">未用样本也可确认，但不会显示一致性</span>
          )}
        </div>
      </Group>
      ) : null}

      <Group
        title="课外维度成绩"
        note="CSV / XLSX"
        footer="成绩单列名含「学号」或「姓名」，以及要导入的维度名；分数可写 A–E 或 0–100。导入后维度重新计入总分，并标记为已打分。"
      >
        {excludedDims.length ? (
          <>
            <div className="list-row" style={{ display: "block" }}>
              <div className="t-body">
                {excludedDims
                  .map((item) =>
                    externalDims[item.name]
                      ? `${item.name}（${externalDims[item.name]} 人）`
                      : item.name
                  )
                  .join("、")}
              </div>
              <div className="row-sub" style={{ marginTop: 4 }}>
                {data?.external?.file ? `已导入 ${data.external.file}` : "尚未导入成绩单"}
              </div>
            </div>
            <Dropzone
              accept=".csv,.xlsx"
              selected={externalFile ? [externalFile] : []}
              title="拖拽成绩单到这里"
              hint="学号 / 姓名 + 停用维度列；A–E 或 0–100"
              onFiles={(files) => setExternalFile(files[0])}
              disabled={externalBusy}
            />
            <div className="list-row" style={{ gap: 8 }}>
              <Button
                variant="filled"
                icon="upload"
                disabled={!externalFile || externalBusy || dirty}
                loading={externalBusy}
                onClick={uploadExternal}
              >
                导入并合并
              </Button>
              {externalFile ? (
                <Button variant="plain" onClick={() => setExternalFile(null)}>
                  清除
                </Button>
              ) : null}
            </div>
          </>
        ) : (
          <div
            className="list-row"
            data-disabled="true"
            title="没有停用的维度，暂时不需要成绩单"
            style={{ opacity: 0.5, cursor: "not-allowed" }}
          >
            <span className="row-sub">没有停用的维度，这项操作不可用</span>
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

      <Sheet
        open={Boolean(reader)}
        wide
        title={reader?.filename || "原文"}
        text="样本报告正文，只读"
        onClose={() => setReader(null)}
        footer={
          <Button variant="filled" onClick={() => setReader(null)}>
            关闭
          </Button>
        }
      >
        {readerBusy ? <Spinner label="读取原文…" /> : <Prose text={readerText} />}
      </Sheet>
    </>
  );
}
