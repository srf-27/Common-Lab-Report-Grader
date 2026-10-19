import { useMemo, useState } from "react";
import { errorText, getJSON, postForm } from "../lib/api";
import { studentText } from "../lib/format";
import { useData } from "../lib/hooks";
import { navigate } from "../lib/router";
import { toast } from "../lib/toast";
import {
  Badge,
  Banner,
  Button,
  Empty,
  Group,
  Icon,
  LinkButton,
  PageHead,
  Spinner,
} from "../ui";

export default function Select() {
  const { data, error, loading } = useData("/api/select");
  const [selected, setSelected] = useState(() => new Set());
  const [busy, setBusy] = useState(false);

  const groups = data?.groups || [];
  const total = data?.total || 0;
  const ungraded = useMemo(
    () => groups.reduce((sum, group) => sum + group.reports.filter((r) => !r.graded).length, 0),
    [groups]
  );

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
      await postForm("/start_grading", { report_ids: [...selected] });
      const status = await getJSON("/grading_status").catch(() => null);
      if (status?.phase === "running") {
        navigate("/app/progress");
      } else {
        toast("未能开始评分：同一学生只能勾选一份报告", "danger");
      }
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
        <Group title="待评报告" note={`${total} 份 · ${ungraded} 份未评`}>
          {groups.map((group) => {
            const selectedInGroup = group.reports.filter((report) => selected.has(report.filename));
            return (
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
                      {report.graded ? <Badge tone="warn">已评过</Badge> : null}
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
                {group.multi && selectedInGroup.length === 0 ? null : null}
              </div>
            );
          })}
        </Group>
      ) : null}

      {total ? (
        <div className="action-bar">
          <div className="grow">
            <div className="t-subhead" style={{ fontWeight: 600 }}>
              已选 {selected.size} 份
            </div>
            <div className="t-caption c-secondary">评分期间可取消，未评的报告下次再选</div>
          </div>
          {selected.size ? (
            <Button variant="plain" onClick={() => setSelected(new Set())}>
              清除
            </Button>
          ) : null}
          <Button
            variant="filled"
            icon="play"
            disabled={!selected.size || busy || !data?.hasRubric}
            loading={busy}
            onClick={start}
          >
            开始评分
          </Button>
        </div>
      ) : null}
    </>
  );
}
