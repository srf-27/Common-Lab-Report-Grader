import { useMemo, useState } from "react";
import { errorText, getJSON, postFormJSON } from "../lib/api";
import { statusMeta, studentText } from "../lib/format";
import { useData } from "../lib/hooks";
import { navigate } from "../lib/router";
import { toast } from "../lib/toast";
import {
  Badge,
  Banner,
  Button,
  Chip,
  Empty,
  Group,
  Icon,
  LinkButton,
  PageHead,
  Spinner,
} from "../ui";

const FLAGGED = ["flagged_injection", "blocked_safety", "llm_failed", "detection_failed", "audit_truncated"];

const FILTERS = [
  { key: "all", label: "全部" },
  { key: "pending", label: "未评分" },
  { key: "stale", label: "需重评" },
  { key: "graded", label: "已评分" },
  { key: "flagged", label: "被标记" },
];

export default function Select() {
  const { data, error, loading } = useData("/api/select");
  const [selected, setSelected] = useState(() => new Set());
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("all");

  const groups = data?.groups || [];
  const total = data?.total || 0;
  const ungraded = useMemo(
    () => groups.reduce((sum, group) => sum + group.reports.filter((r) => !r.stale && !r.graded).length, 0),
    [groups]
  );

  const matched = (report) => {
    if (filter === "pending") return !report.graded && !report.stale;
    if (filter === "stale") return Boolean(report.stale);
    if (filter === "graded") return report.graded && !report.stale;
    if (filter === "flagged") return FLAGGED.includes(report.status);
    return true;
  };

  const counts = useMemo(() => {
    const all = groups.flatMap((group) => group.reports);
    return {
      all: all.length,
      pending: all.filter((r) => !r.graded && !r.stale).length,
      stale: all.filter((r) => r.stale).length,
      graded: all.filter((r) => r.graded && !r.stale).length,
      flagged: all.filter((r) => FLAGGED.includes(r.status)).length,
    };
  }, [groups]);

  const visibleGroups = useMemo(
    () =>
      groups
        .map((group) => ({ ...group, reports: group.reports.filter(matched) }))
        .filter((group) => group.reports.length),
    [groups, filter]
  );

  const selectedReports = useMemo(
    () => groups.flatMap((group) => group.reports).filter((r) => selected.has(r.filename)),
    [groups, selected]
  );
  const reselecting = selectedReports.some((r) => r.graded || r.stale);

  const toggle = (group, report) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(report.filename)) {
        next.delete(report.filename);
        return next;
      }
      if (group.multi) group.reports.forEach((item) => next.delete(item.filename));
      next.add(report.filename);
      return next;
    });
  };

  const start = async () => {
    if (!selected.size) return;
    setBusy(true);
    try {
      const result = await postFormJSON("/start_grading", { report_ids: [...selected] });
      if (result.running) {
        toast(result.message || "已有评分任务在跑", "ok");
        navigate("/app/progress");
        return;
      }
      if (!result.started) {
        toast(result.message || "没有可评的报告", "danger");
        return;
      }
      toast(`已开始评分 ${result.started} 份`, "ok");
      navigate("/app/progress");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHead
        title="选择评分"
        sub={data?.hint || `${total} 份待评报告 · 同一学生只能选一份，已终审的报告不出现在这里`}
        actions={
          selected.size ? (
            <Button variant="plain" onClick={() => setSelected(new Set())}>
              清除选择
            </Button>
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

      {data && !data.hasRubric ? (
        <div style={{ marginBottom: 16 }}>
          <Banner
            tone="warn"
            icon="alert"
            actions={
              <LinkButton to="/app/rubric" size="sm">
                去配置
              </LinkButton>
            }
          >
            还没有评分细则，评分不会启动。
          </Banner>
        </div>
      ) : null}

      {data?.hasRubric && data.rubricConfirmed === false ? (
        <div style={{ marginBottom: 16 }}>
          <Banner
            tone="warn"
            icon="alert"
            actions={
              <LinkButton to="/app/rubric" size="sm">
                去校准
              </LinkButton>
            }
          >
            评分细则还没确认：先用 1–5 份样本校准并确认，才能开始评分。
          </Banner>
        </div>
      ) : null}

      {data?.error ? (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="danger" icon="alert">
            {data.error}
          </Banner>
        </div>
      ) : null}

      {loading && !data ? <Spinner label="整理待评报告…" /> : null}

      {data && !total ? (
        <Empty
          icon="reports"
          title="没有可评的报告"
          text="报告都已终审，或者还没上传报告。"
          action={
            <LinkButton to="/app/reports" variant="filled" icon="reports">
              去上传报告
            </LinkButton>
          }
        />
      ) : null}

      {total ? (
        <>
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
          </div>

          {visibleGroups.length ? (
            <Group title="待评报告" note={`${visibleGroups.reduce((n, g) => n + g.reports.length, 0)} 份`}>
              {visibleGroups.map((group) => (
                <div key={group.label} style={{ display: "contents" }}>
                  <div
                    className="list-row"
                    style={{ minHeight: 36, background: "var(--surface-2)", paddingTop: 6, paddingBottom: 6 }}
                  >
                    <span className="row-main">
                      <span className="t-footnote c-secondary" style={{ fontWeight: 600 }}>
                        {group.label}
                      </span>
                    </span>
                    <span className="t-caption c-secondary">
                      {group.reports.length} 份{group.multi ? " · 只能选一份" : ""}
                    </span>
                  </div>
                  {group.reports.map((report) => {
                    const active = selected.has(report.filename);
                    const meta = statusMeta(report.status);
                    return (
                      <button
                        key={report.filename}
                        type="button"
                        className="list-row"
                        data-interactive="true"
                        data-selected={active ? "true" : undefined}
                        aria-pressed={active}
                        onClick={() => toggle(group, report)}
                      >
                        <span className="row-main">
                          <span className="row-title" style={{ display: "block" }}>
                            {report.filename}
                          </span>
                          <span className="row-sub" style={{ display: "block" }}>
                            {studentText(report.student, data.fields)}
                            {report.pages ? ` · ${report.pages} 页` : ""}
                            {report.images ? ` · ${report.images} 图` : ""}
                          </span>
                        </span>
                        {report.stale ? <Badge tone="warn">需重评</Badge> : null}
                        {!report.stale && report.graded ? <Badge tone="ok">已评分</Badge> : null}
                        {report.status && report.status !== "graded" ? (
                          <Badge tone={meta.tone}>{meta.label}</Badge>
                        ) : null}
                        {report.scanned ? <Badge>扫描件</Badge> : null}
                        <span
                          aria-hidden="true"
                          style={{
                            width: 22,
                            height: 22,
                            display: "grid",
                            placeItems: "center",
                            color: "var(--tint)",
                            opacity: active ? 1 : 0,
                          }}
                        >
                          <Icon name="check" size={18} />
                        </span>
                      </button>
                    );
                  })}
                </div>
              ))}
            </Group>
          ) : (
            <Empty
              icon="select"
              title="这个筛选下没有报告"
              text="换个筛选条件，或看「全部」。"
              action={
                <Button onClick={() => setFilter("all")}>看全部</Button>
              }
            />
          )}
        </>
      ) : null}

      {total ? (
        <div className="action-bar">
          <div className="grow">
            <div className="t-subhead" style={{ fontWeight: 600 }}>
              已选 {selected.size} 份
            </div>
            <div className="t-caption c-secondary">
              {reselecting ? "包含已评过的报告，会重新调用模型并产生费用" : "评分期间可取消，未评的报告下次再选"}
            </div>
          </div>
          {selected.size ? (
            <Button variant="plain" onClick={() => setSelected(new Set())}>
              清除
            </Button>
          ) : null}
          <Button
            variant="filled"
            icon="play"
            disabled={!selected.size || busy || !data?.hasRubric || data?.rubricConfirmed === false}
            loading={busy}
            onClick={start}
          >
            {reselecting ? `重新评分 ${selected.size} 份` : "开始评分"}
          </Button>
        </div>
      ) : null}
    </>
  );
}
