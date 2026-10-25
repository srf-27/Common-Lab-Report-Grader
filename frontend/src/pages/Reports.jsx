import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { errorText, getJSON, postEmpty, postForm } from "../lib/api";
import { studentText } from "../lib/format";
import { useData, usePoll } from "../lib/hooks";
import { Link } from "../lib/router";
import { toast } from "../lib/toast";
import {
  Badge,
  Banner,
  Button,
  Chip,
  Dropzone,
  Empty,
  Field,
  Group,
  Icon,
  IconButton,
  PageHead,
  Progress,
  Sheet,
  Spinner,
} from "../ui";

const FILTERS = [
  { key: "all", label: "全部" },
  { key: "pending", label: "未评分" },
  { key: "graded", label: "已评分" },
  { key: "approved", label: "已终审" },
  { key: "scanned", label: "扫描件" },
];

export default function Reports() {
  const { data, error, loading, load } = useData("/api/reports");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [task, setTask] = useState(null);
  const [polling, setPolling] = useState(false);
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(null);
  const [student, setStudent] = useState({});
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    getJSON("/task_status")
      .then((next) => {
        if (next?.kind === "reports" && next.status === "running") {
          setTask(next);
          setPolling(true);
        }
      })
      .catch(() => {});
    return () => {
      mounted.current = false;
    };
  }, []);

  const tick = useCallback(async () => {
    try {
      const next = await getJSON("/task_status");
      if (!mounted.current) return;
      if (next?.kind !== "reports") return;
      setTask(next);
      if (next.status !== "running") {
        setPolling(false);
        if (next.status === "done") {
          toast(next.detail || "报告已提取完成", "ok");
          load();
        } else if (next.status === "error") {
          toast(next.error || "提取失败", "danger");
        }
      }
    } catch (err) {
      setPolling(false);
      toast(errorText(err), "danger");
    }
  }, [load]);

  usePoll(tick, 1200, polling);

  const reports = data?.reports || [];
  const fields = data?.fields || [];

  const counts = useMemo(
    () => ({
      all: reports.length,
      pending: reports.filter((item) => !item.graded).length,
      graded: reports.filter((item) => item.graded).length,
      approved: reports.filter((item) => item.approved).length,
      scanned: reports.filter((item) => item.scanned).length,
    }),
    [reports]
  );

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return reports.filter((item) => {
      if (filter === "pending" && item.graded) return false;
      if (filter === "graded" && !item.graded) return false;
      if (filter === "approved" && !item.approved) return false;
      if (filter === "scanned" && !item.scanned) return false;
      if (!needle) return true;
      return (
        item.filename.toLowerCase().includes(needle) ||
        studentText(item.student, fields).toLowerCase().includes(needle)
      );
    });
  }, [reports, filter, query, fields]);

  const upload = async () => {
    if (!files.length) return toast("请先选择报告文件", "danger");
    setBusy(true);
    try {
      await postForm("/upload_reports", { report_files: files });
      await postForm("/process_reports", {});
      const next = await getJSON("/task_status");
      if (next?.kind !== "reports" || next.status !== "running") {
        toast("没能开始提取，请重试", "danger");
        return;
      }
      setTask(next);
      setPolling(true);
      setFiles([]);
      toast(`已上传 ${files.length} 个文件，开始提取正文`, "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  const saveStudent = async () => {
    if (!editing) return;
    setBusy(true);
    try {
      const payload = { next: "/app/reports" };
      fields.forEach((field) => {
        payload[`student::${field}`] = student[field] || "";
      });
      await postForm(`/update_student/${encodeURIComponent(editing.filename)}`, payload);
      await load();
      toast("学生信息已更新", "ok");
      setEditing(null);
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHead
        title="实验报告"
        sub={`${reports.length} 份已提取 · ${counts.graded} 份已评分 · ${counts.approved} 份已终审`}
        actions={
          data?.downloads?.excel ? (
            <a className="btn btn-tinted" href={`/download/${data.downloads.excel}`}>
              <Icon name="download" size={15} />
              成绩 Excel
            </a>
          ) : null
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
            title={task.status === "running" ? "正在提取报告" : "上次提取"}
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
              <Progress value={task.progress || 0} tone={task.status === "error" ? "danger" : undefined} />
              <div className="spread" style={{ marginTop: 8 }}>
                <span className="row-sub" style={{ whiteSpace: "normal" }}>
                  {task.detail || task.stage || "准备中"}
                  {task.total ? ` · ${task.done || 0}/${task.total}` : ""}
                </span>
                <span className="t-footnote tnum c-secondary">{task.progress || 0}%</span>
              </div>
            </div>
          </Group>
        </div>
      ) : null}

      <Group
        title="上传报告"
        note="PDF / DOCX / DOC / MD / ZIP；HTML / PPTX / XLSX / EPUB 经 markitdown 插件转换"
        footer="提取会解析正文、插图与学生信息；扫描页调用 OCR。同一学生在评分时只能选一份。"
      >
        <Dropzone
          accept=".pdf,.docx,.doc,.md,.zip,.rar,.7z,.html,.htm,.pptx,.xlsx,.epub"
          multiple
          selected={files}
          title="拖拽报告到这里"
          hint="支持 PDF / DOCX / DOC / MD / ZIP；HTML / PPTX / XLSX / EPUB 走 markitdown 转换；可多选，也可整包拖入"
          onFiles={setFiles}
          disabled={polling}
        />
        <div className="list-row" style={{ gap: 8 }}>
          <Button
            variant="filled"
            icon="upload"
            disabled={!files.length || busy || polling}
            loading={busy && !polling}
            onClick={upload}
          >
            上传并提取
          </Button>
          {files.length ? (
            <Button variant="plain" onClick={() => setFiles([])}>
              清除
            </Button>
          ) : null}
          <span className="row-sub" style={{ marginLeft: "auto" }}>
            同文重复会自动去重
          </span>
        </div>
      </Group>

      <div className="row-wrap" style={{ marginBottom: 12 }}>
        {FILTERS.map((item) => (
          <Chip
            key={item.key}
            active={filter === item.key}
            count={counts[item.key]}
            onClick={() => setFilter(item.key)}
          >
            {item.label}
          </Chip>
        ))}
        <label className="row grow" style={{ position: "relative", minWidth: 180 }}>
          <span className="sr-only">搜索报告</span>
          <Icon
            name="search"
            size={15}
            style={{ position: "absolute", left: 10, color: "var(--label-3)" }}
          />
          <input
            className="input"
            style={{ paddingLeft: 32 }}
            placeholder="搜索文件名或学生"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      </div>

      <Group title="报告列表" note={`${visible.length} / ${reports.length}`}>
        {loading && !reports.length ? <Spinner label="读取报告…" /> : null}

        {!loading && !visible.length ? (
          <div style={{ padding: 16 }}>
            <Empty
              icon="reports"
              title={reports.length ? "没有符合条件的报告" : "还没有提取过报告"}
              text={
                reports.length
                  ? "换个筛选条件或清空搜索词。"
                  : "上传单份报告或压缩包后，系统会提取正文、插图与学生信息。"
              }
            />
          </div>
        ) : null}

        {visible.map((item) => (
          <div className="list-row" key={item.filename} data-interactive="true">
            <Link
              to={`/app/report/${encodeURIComponent(item.filename)}`}
              className="row-overlay"
              aria-label={`打开 ${item.filename}`}
            />
            <span className="row-main">
              <span className="row-title" style={{ display: "block" }}>
                {item.filename}
              </span>
              <span className="row-sub" style={{ display: "block" }}>
                {studentText(item.student, fields)}
                {item.paragraphs ? ` · ${item.paragraphs} 段` : ""}
                {item.images ? ` · ${item.images} 图` : ""}
              </span>
            </span>
            <span className="row-wrap" style={{ gap: 4 }}>
              {item.graded ? <Badge tone="ok">已评分</Badge> : <Badge>未评分</Badge>}
              {item.approved ? <Badge tone="accent">已终审</Badge> : null}
              {item.scanned ? <Badge tone="warn">扫描件</Badge> : null}
            </span>
            <IconButton
              icon="pen"
              label="编辑学生信息"
              onClick={() => {
                setEditing(item);
                setStudent({ ...(item.student || {}) });
              }}
            />
            {item.hasOriginal ? (
              <a
                className="icon-btn"
                href={`/report_original/${encodeURIComponent(item.filename)}`}
                target="_blank"
                rel="noreferrer"
                aria-label="打开原文"
                title="打开原文"
              >
                <Icon name="external" size={18} />
              </a>
            ) : (
              <IconButton icon="external" label="原文不在工作目录" disabled />
            )}
            <Icon name="chevronRight" size={15} className="row-chevron" />
          </div>
        ))}
      </Group>

      {data?.downloads ? (
        <Group title="导出" footer="未知状态一律写 N/A，不会把失败报告算成 0 分。">
          {[
            ["excel", "成绩 Excel", "所有已评分报告与逐维度等级"],
            ["json", "评分 JSON", "完整判级数据，含证据与理由"],
            ["flagged", "被标记人员", "学号不在名册或姓名不一致的学生"],
          ].map(([key, label, sub]) => {
            const href = data.downloads[key];
            if (!href) {
              return (
                <div
                  className="list-row"
                  key={key}
                  data-disabled="true"
                  title="当前没有可导出的内容"
                  style={{ opacity: 0.5, cursor: "not-allowed" }}
                >
                  <span className="row-icon">
                    <Icon name="download" size={16} />
                  </span>
                  <span className="row-main">
                    <span className="row-title" style={{ display: "block" }}>
                      {label}
                    </span>
                    <span className="row-sub" style={{ display: "block" }}>
                      {sub}
                    </span>
                  </span>
                  <Badge>暂无</Badge>
                </div>
              );
            }
            return (
              <a className="list-row" key={key} href={`/download/${href}`}>
                <span className="row-icon">
                  <Icon name="download" size={16} />
                </span>
                <span className="row-main">
                  <span className="row-title" style={{ display: "block" }}>
                    {label}
                  </span>
                  <span className="row-sub" style={{ display: "block" }}>
                    {sub}
                  </span>
                </span>
                <Icon name="chevronRight" size={15} className="row-chevron" />
              </a>
            );
          })}
        </Group>
      ) : null}

      <Sheet
        open={Boolean(editing)}
        title="学生信息"
        text="名册存在时，学号与姓名要和名册一致，否则会在花名册页被标为可疑。"
        onClose={() => setEditing(null)}
        footer={
          <>
            <Button onClick={() => setEditing(null)}>取消</Button>
            <Button variant="filled" loading={busy} onClick={saveStudent}>
              保存
            </Button>
          </>
        }
      >
        <div className="grid-2">
          {fields.map((field) => (
            <Field key={field} label={field}>
              {(id) => (
                <input
                  id={id}
                  className="input"
                  value={student[field] || ""}
                  onChange={(event) => setStudent({ ...student, [field]: event.target.value })}
                />
              )}
            </Field>
          ))}
        </div>
      </Sheet>
    </>
  );
}
