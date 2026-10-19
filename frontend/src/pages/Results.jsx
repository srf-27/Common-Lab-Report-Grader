import { useEffect, useMemo, useState } from "react";
import { errorText, postForm } from "../lib/api";
import { statusMeta, studentText, timeText, totalScore } from "../lib/format";
import { useData } from "../lib/hooks";
import { navigate } from "../lib/router";
import { toast } from "../lib/toast";
import {
  Badge,
  Banner,
  Button,
  Chip,
  Disclosure,
  Empty,
  Field,
  Group,
  Icon,
  LevelPicker,
  LinkButton,
  PageHead,
  Progress,
  Sheet,
  Spinner,
  Stat,
} from "../ui";

const ATTENTION = [
  "flagged_injection",
  "blocked_safety",
  "llm_failed",
  "detection_failed",
  "audit_truncated",
];

const FILTERS = [
  { key: "all", label: "全部" },
  { key: "graded", label: "已评分" },
  { key: "attention", label: "需人工" },
  { key: "plagiarism", label: "疑似重复" },
  { key: "unapproved", label: "未终审" },
];

function draftFrom(result) {
  const levels = {};
  const reasons = {};
  Object.entries(result?.grading?.scores || {}).forEach(([name, score]) => {
    levels[name] = score.level || "C";
    reasons[name] = score.teacher_reasoning || "";
  });
  return { levels, reasons };
}

export default function Results() {
  const { data, error, loading, load } = useData("/api/results");
  const [filter, setFilter] = useState("all");
  const [drafts, setDrafts] = useState({});
  const [busyId, setBusyId] = useState("");
  const [regrading, setRegrading] = useState(null);
  const [corrections, setCorrections] = useState("");

  useEffect(() => {
    if (!data) return;
    const next = {};
    data.results.forEach((result) => {
      if (result.status === "graded") next[result.report_id] = draftFrom(result);
    });
    setDrafts(next);
  }, [data]);

  const counts = data?.counts || {};
  const approved = useMemo(() => new Set(data?.approvedIds || []), [data]);
  const stale = useMemo(() => new Set(data?.staleIds || []), [data]);

  const visible = useMemo(() => {
    const results = data?.results || [];
    return results.filter((result) => {
      if (filter === "graded") return result.status === "graded";
      if (filter === "attention") return ATTENTION.includes(result.status);
      if (filter === "plagiarism") return Boolean(result.similarity_warnings?.length);
      if (filter === "unapproved") return !approved.has(result.report_id);
      return true;
    });
  }, [data, filter, approved]);

  const attention = (counts.injection || 0) + (counts.blocked || 0) + (counts.failed || 0);

  const dirty = (result) => {
    const draft = drafts[result.report_id];
    if (!draft) return false;
    return Object.entries(result.grading.scores || {}).some(
      ([name, score]) =>
        draft.levels[name] !== score.level ||
        (draft.reasons[name] || "") !== (score.teacher_reasoning || "")
    );
  };

  const saveScores = async (result) => {
    const draft = drafts[result.report_id];
    if (!draft) return;
    setBusyId(result.report_id);
    try {
      const payload = { report_id: result.report_id, next: "/app/results" };
      Object.entries(draft.levels).forEach(([name, level]) => {
        payload[`level::${name}`] = level;
        payload[`reason::${name}`] = draft.reasons[name] || "";
      });
      await postForm("/update_scores", payload);
      await load();
      toast("成绩已更新", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusyId("");
    }
  };

  const approve = async (result) => {
    setBusyId(result.report_id);
    try {
      await postForm(`/approve_report/${encodeURIComponent(result.report_id)}`, {
        next: "/app/results",
      });
      await load();
      toast("已终审并写入案例库", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusyId("");
    }
  };

  const regrade = async () => {
    if (!regrading) return;
    setBusyId(regrading.report_id);
    try {
      await postForm(`/regrade/${encodeURIComponent(regrading.report_id)}`, {
        corrections,
        next: "/app/results",
      });
      toast("已提交重评", "ok");
      navigate("/app/progress");
    } catch (err) {
      toast(errorText(err), "danger");
      setBusyId("");
    }
  };

  return (
    <>
      <PageHead
        title="评分结果"
        sub={`${counts.all || 0} 份结果 · ${counts.unapproved || 0} 份待终审 · 终审后的报告进入本课程案例库`}
        actions={
          data?.downloads?.excel ? (
            <a className="btn btn-filled" href={`/download/${data.downloads.excel}`}>
              <Icon name="download" size={15} />
              成绩 Excel
            </a>
          ) : (
            <Button variant="filled" icon="download" disabled>
              成绩 Excel
            </Button>
          )
        }
      />

      {error ? (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="danger" icon="alert">
            {error}
          </Banner>
        </div>
      ) : null}

      {data?.running ? (
        <div style={{ marginBottom: 18 }}>
          <Group title="评分仍在进行" actions={<LinkButton to="/app/progress" size="sm">查看进度</LinkButton>}>
            <div className="list-row" style={{ display: "block" }}>
              <Progress
                value={counts.all ? (counts.graded / counts.all) * 100 : 12}
              />
              <p className="t-footnote c-secondary" style={{ marginTop: 8 }}>
                结果会随评分逐份出现，这里的按钮在评分期间不可用。
              </p>
            </div>
          </Group>
        </div>
      ) : null}

      <div className="stat-grid" style={{ marginBottom: 18 }}>
        <Stat label="结果总数" value={counts.all || 0} suffix="份" />
        <Stat label="已评分" value={counts.graded || 0} suffix="份" />
        <Stat label="需人工处理" value={attention} suffix="份" />
        <Stat label="待终审" value={counts.unapproved || 0} suffix="份" />
      </div>

      <div className="row-wrap" style={{ marginBottom: 12 }}>
        {FILTERS.map((item) => (
          <Chip
            key={item.key}
            active={filter === item.key}
            count={
              item.key === "all"
                ? counts.all || 0
                : item.key === "graded"
                  ? counts.graded || 0
                  : item.key === "attention"
                    ? attention
                    : item.key === "plagiarism"
                      ? counts.plagiarism || 0
                      : counts.unapproved || 0
            }
            onClick={() => setFilter(item.key)}
          >
            {item.label}
          </Chip>
        ))}
      </div>

      {loading && !data ? <Spinner label="读取评分结果…" /> : null}

      {!loading && !(data?.results || []).length ? (
        <Empty
          icon="results"
          title="还没有评分结果"
          text={
            data?.hasReports
              ? "在「选择评分」里勾选报告开始，评分完成后结果会出现在这里。"
              : "先上传报告并生成评分细则，再开始评分。"
          }
          action={
            <LinkButton
              to={data?.hasReports ? "/app/select" : "/app/reports"}
              variant="filled"
              icon={data?.hasReports ? "select" : "reports"}
            >
              {data?.hasReports ? "选择报告" : "上传报告"}
            </LinkButton>
          }
        />
      ) : null}

      {visible.length ? (
        <Group title="逐份结果" note={`${visible.length} 份`}>
          {visible.map((result) => {
            const meta = statusMeta(result.status);
            const draft = drafts[result.report_id] || { levels: {}, reasons: {} };
            const isApproved = approved.has(result.report_id);
            const isStale = stale.has(result.report_id);
            const graded = result.status === "graded";
            const cardBusy = busyId === result.report_id;

            return (
              <Disclosure
                key={result.report_id}
                summary={
                  <span style={{ display: "block", minWidth: 0 }}>
                    <span className="row-title" style={{ display: "block" }}>
                      {studentText(data.students?.[result.report_id], data.fields)}
                    </span>
                    <span className="row-sub" style={{ display: "block" }}>
                      {result.report_id}
                    </span>
                  </span>
                }
                meta={
                  <>
                    {isApproved ? <Badge tone="accent">已终审</Badge> : null}
                    {isStale && graded ? <Badge tone="warn">需重评</Badge> : null}
                    {result.similarity_warnings?.length ? (
                      <Badge tone="warn">重复 {result.similarity_warnings.length}</Badge>
                    ) : null}
                    {graded ? null : <Badge tone={meta.tone}>{meta.label}</Badge>}
                    <span className="t-title-3 tnum" style={{ minWidth: 40, textAlign: "right" }}>
                      {totalScore(result) ?? "—"}
                    </span>
                  </>
                }
              >
                {graded ? (
                  <>
                    <div className="stack" style={{ gap: 14 }}>
                      {Object.entries(result.grading.scores || {}).map(([name, score]) => (
                        <div key={name}>
                          <div className="dim-row">
                            <span className="row" style={{ minWidth: 0, gap: 6 }}>
                              <span className="t-subhead" style={{ fontWeight: 600 }}>
                                {name}
                              </span>
                              {score.ai_level ? <Badge outline>AI {score.ai_level}</Badge> : null}
                              {score.teacher_adjusted ? <Badge tone="warn">已改</Badge> : null}
                            </span>
                            <LevelPicker
                              value={draft.levels[name] || score.level}
                              disabled={data.running || isApproved}
                              onChange={(level) =>
                                setDrafts((prev) => ({
                                  ...prev,
                                  [result.report_id]: {
                                    ...draft,
                                    levels: { ...draft.levels, [name]: level },
                                  },
                                }))
                              }
                            />
                          </div>
                          {score.reasoning ? (
                            <p className="t-footnote c-secondary" style={{ marginTop: 6, lineHeight: 1.5 }}>
                              {score.reasoning}
                            </p>
                          ) : null}
                          {score.evidence ? (
                            <div className="quote" style={{ marginTop: 6 }}>
                              {score.evidence}
                            </div>
                          ) : null}
                          <input
                            className="cell-input"
                            style={{ marginTop: 6, background: "var(--fill)", minHeight: 34 }}
                            placeholder="教师说明（可选，会进入重评提示词）"
                            value={draft.reasons[name] || ""}
                            aria-label={`${name} 教师说明`}
                            disabled={data.running || isApproved}
                            onChange={(event) =>
                              setDrafts((prev) => ({
                                ...prev,
                                [result.report_id]: {
                                  ...draft,
                                  reasons: { ...draft.reasons, [name]: event.target.value },
                                },
                              }))
                            }
                          />
                        </div>
                      ))}
                    </div>

                    <div className="kv" style={{ marginTop: 14 }}>
                      <div>
                        <div className="kv-key">总分</div>
                        <div className="kv-val">{totalScore(result) ?? "—"}</div>
                      </div>
                      <div>
                        <div className="kv-key">机械 / 语义</div>
                        <div className="kv-val">
                          {result.grading.subtotals?.procedural ?? "—"} /{" "}
                          {result.grading.subtotals?.semantic ?? "—"}
                        </div>
                      </div>
                      <div>
                        <div className="kv-key">评分时间</div>
                        <div className="kv-val">{timeText(result.graded_at)}</div>
                      </div>
                    </div>

                    <div className="row-wrap" style={{ marginTop: 14 }}>
                      <Button
                        size="sm"
                        icon="check"
                        disabled={!dirty(result) || cardBusy || isApproved}
                        loading={cardBusy && dirty(result)}
                        onClick={() => saveScores(result)}
                      >
                        保存修改
                      </Button>
                      <Button
                        size="sm"
                        variant={isApproved ? "tinted" : "tinted"}
                        icon="lock"
                        disabled={cardBusy || isApproved || isStale || data.running}
                        title={isStale ? "细则已修改，请先重评" : undefined}
                        onClick={() => approve(result)}
                      >
                        {isApproved ? "已终审" : "终审入库"}
                      </Button>
                      <Button
                        size="sm"
                        icon="refresh"
                        disabled={cardBusy || data.running}
                        onClick={() => {
                          setCorrections("");
                          setRegrading(result);
                        }}
                      >
                        打回重评
                      </Button>
                      <LinkButton
                        to={`/app/report/${encodeURIComponent(result.report_id)}`}
                        size="sm"
                        icon="eye"
                      >
                        维度详情
                      </LinkButton>
                    </div>

                    {isStale ? (
                      <div style={{ marginTop: 10 }}>
                        <Banner tone="warn" icon="alert">
                          评分细则在上次评分后被修改，这份结果需要重评后才能终审。
                        </Banner>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <>
                    <Banner tone={meta.tone === "danger" ? "danger" : "warn"} icon="alert">
                      <div>
                        <strong>{meta.label}</strong>
                        {result.error ? `：${result.error}` : ""}
                        {result.injection_details?.evidence ? `：${result.injection_details.evidence}` : ""}
                      </div>
                      {result.injection_details?.hits?.length ? (
                        <div style={{ marginTop: 4 }}>{result.injection_details.hits.join("；")}</div>
                      ) : null}
                    </Banner>
                    <div className="row-wrap" style={{ marginTop: 12 }}>
                      <Button
                        size="sm"
                        variant="filled"
                        icon="refresh"
                        disabled={cardBusy || data.running}
                        onClick={() => {
                          setCorrections("");
                          setRegrading(result);
                        }}
                      >
                        重新评分
                      </Button>
                      <LinkButton
                        to={`/app/report/${encodeURIComponent(result.report_id)}`}
                        size="sm"
                        icon="eye"
                      >
                        查看报告
                      </LinkButton>
                    </div>
                  </>
                )}
              </Disclosure>
            );
          })}
        </Group>
      ) : null}

      {data?.agreement?.overall?.n ? (
        <Group
          title="与教师真值的一致性"
          note={`${data.agreement.overall.n} 组对照`}
          footer="κ 0.61 以上通常视为高度一致。"
        >
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>维度</th>
                  <th style={{ textAlign: "right" }}>n</th>
                  <th style={{ textAlign: "right" }}>Cohen's κ</th>
                  <th style={{ textAlign: "right" }}>加权 κ</th>
                  <th style={{ textAlign: "right" }}>Krippendorff's α</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.agreement.dimensions || {})
                  .filter(([, item]) => item.n)
                  .map(([name, item]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td className="tnum" style={{ textAlign: "right" }}>{item.n}</td>
                      <td className="tnum" style={{ textAlign: "right" }}>{item.cohen_kappa ?? "—"}</td>
                      <td className="tnum" style={{ textAlign: "right" }}>{item.weighted_kappa ?? "—"}</td>
                      <td className="tnum" style={{ textAlign: "right" }}>{item.krippendorff_alpha ?? "—"}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Group>
      ) : null}

      {data?.downloads ? (
        <Group title="导出" footer="未知状态一律写 N/A，不会把失败报告算成 0 分。">
          {[
            ["excel", "成绩 Excel"],
            ["json", "评分 JSON"],
            ["flagged", "被标记人员"],
          ].map(([key, label]) =>
            data.downloads[key] ? (
              <a className="list-row" key={key} href={`/download/${data.downloads[key]}`}>
                <span className="row-icon">
                  <Icon name="download" size={16} />
                </span>
                <span className="row-main">
                  <span className="row-title" style={{ display: "block" }}>
                    {label}
                  </span>
                </span>
                <Icon name="chevronRight" size={15} className="row-chevron" />
              </a>
            ) : null
          )}
        </Group>
      ) : null}

      <Sheet
        open={Boolean(regrading)}
        title="打回重评"
        text={regrading ? `${regrading.report_id} 会重新判级，已有的教师修改会被覆盖。` : ""}
        onClose={() => setRegrading(null)}
        footer={
          <>
            <Button onClick={() => setRegrading(null)}>取消</Button>
            <Button variant="filled" loading={busyId === regrading?.report_id} onClick={regrade}>
              开始重评
            </Button>
          </>
        }
      >
        <Field label="修改意见" hint="会作为额外指令进入重评提示词，例如「实验原理少讲了误差来源」">
          {(id) => (
            <textarea
              id={id}
              className="textarea"
              value={corrections}
              onChange={(event) => setCorrections(event.target.value)}
              placeholder="可选"
            />
          )}
        </Field>
      </Sheet>
    </>
  );
}
