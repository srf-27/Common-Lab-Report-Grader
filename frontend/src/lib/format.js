export const LEVELS = ["A", "B", "C", "D", "E"];

export const LEVEL_LABEL = {
  A: "优秀",
  B: "良好",
  C: "及格",
  D: "不及格",
  E: "未实现",
};

const DEFAULT_FIELDS = ["班级", "学院", "学号", "姓名"];

const STATUS = {
  graded: ["已评分", "ok"],
  flagged_injection: ["疑似注入", "warn"],
  blocked_safety: ["安全拦截", "danger"],
  flagged_duplicate: ["疑似重复", "warn"],
  llm_failed: ["模型失败", "danger"],
  detection_failed: ["检测失败", "warn"],
  audit_truncated: ["超长截断", "warn"],
};

export function statusMeta(status) {
  const [label, tone] = STATUS[status] || [status || "未知", ""];
  return { label, tone };
}

export function totalScore(result) {
  const total = result?.grading?.subtotals?.total;
  return typeof total === "number" ? total : null;
}

export const LEVEL_POINTS = { A: 95, B: 80, C: 60, D: 40, E: 0 };

/* 草稿总分：与后端 compute_subtotals 同口径（只按有分维度的权重折算回百分制） */
export function draftTotal(result, draft, weights) {
  const scores = result?.grading?.scores || {};
  let active = 0;
  let sum = 0;
  Object.entries(scores).forEach(([name, score]) => {
    const points = score.score != null
      ? Number(score.score)
      : LEVEL_POINTS[draft?.levels?.[name] || score.level];
    if (points == null || Number.isNaN(points)) return;
    const weight = weights?.[name] ?? 0;
    active += weight;
    sum += points * weight;
  });
  if (!active) return totalScore(result);
  return Math.round((sum / active) * 10) / 10;
}

export function timeText(ts) {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) return "—";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function studentText(student, fields) {
  const keys = fields?.length ? fields : DEFAULT_FIELDS;
  const parts = keys.map((key) => student?.[key]).filter((v) => v && String(v).trim());
  return parts.length ? parts.join(" · ") : "未识别学生";
}
