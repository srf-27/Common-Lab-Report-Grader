import { useState } from "react";
import { Link } from "../lib/router";
import { useApp } from "../lib/store";
import {
  Badge,
  Banner,
  Button,
  Field,
  Group,
  Icon,
  LinkButton,
  ListRow,
  PageHead,
  Sheet,
  Stat,
} from "../ui";

const STAGE_INDEX = { initial: 0, rubric: 0, grading: 2, review: 3, done: 4 };

const metric = (value) =>
  typeof value === "number" && !Number.isNaN(value) ? value.toFixed(3) : "—";

export default function Workbench() {
  const { boot, switchSession, removeSession } = useApp();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);

  const { rubric, reports, approved, unapproved, stage } = boot;
  const steps = [
    { label: "评分细则", to: "/app/rubric", done: rubric.count > 0 && rubric.confirmed !== false },
    { label: "上传报告", to: "/app/reports", done: reports.total > 0 },
    {
      label: "逐份评分",
      to: "/app/select",
      done: reports.total > 0 && reports.graded >= reports.total,
    },
    { label: "终审入库", to: "/app/results", done: approved > 0 && unapproved === 0 },
    { label: "导出成绩", to: "/app/results", done: stage.key === "done" },
  ];
  const current =
    stage.key === "rubric" && reports.total > 0 && reports.graded < reports.total
      ? 2
      : STAGE_INDEX[stage.key] ?? 0;
  const ready = rubric.count > 0 && reports.total > 0 && rubric.confirmed !== false;

  return (
    <>
      <PageHead
        title="工作台"
        sub={`${boot.session.name} · 按 1 → 5 步顺序准备数据，按钮随数据齐备自动启用。`}
        actions={
          <>
            <LinkButton to="/app/rubric" variant="tinted" icon="rubric">
              评分细则
            </LinkButton>
            {ready ? (
              <LinkButton to="/app/select" variant="filled" icon="play">
                开始评分
              </LinkButton>
            ) : (
              <Button variant="filled" icon="play" disabled>
                开始评分
              </Button>
            )}
          </>
        }
      />

      <div className="steps" aria-label="评阅流程">
        {steps.map((step, index) => (
          <div key={step.label} style={{ display: "contents" }}>
            {index ? <span className="step-sep" aria-hidden="true" /> : null}
            <Link
              className="step"
              to={step.to}
              data-state={index < current ? "done" : index === current ? "current" : "todo"}
            >
              <span className="step-num" aria-hidden="true">
                {index < current ? <Icon name="check" size={11} /> : index + 1}
              </span>
              {step.label}
            </Link>
          </div>
        ))}
      </div>

      <div className="stat-grid" style={{ margin: "14px 0 22px" }}>
        <Stat label="评分维度" value={rubric.count} suffix="个" />
        <Stat label="实验报告" value={reports.total} suffix="份" />
        <Stat label="已评分" value={reports.graded} suffix="份" />
        <Stat label="待终审" value={unapproved} suffix="份" />
      </div>

      <Group title="评阅流程" footer="每一步的产出都会落到当前课程目录，切换课程互不影响。">
        <ListRow
          icon="rubric"
          to="/app/rubric"
          title="评分细则"
          sub={
            rubric.count
              ? `${rubric.count} 个维度，权重合计 100%`
              : rubric.hasUpload
                ? "已上传标准，等待生成细则"
                : "上传评分标准，生成可判级的维度"
          }
          trailing={
            <Badge tone={rubric.count ? "ok" : ""}>{rubric.count ? "已就绪" : "待生成"}</Badge>
          }
          chevron
        />
        <ListRow
          icon="reports"
          to="/app/reports"
          title="实验报告"
          sub={
            reports.total
              ? `已提取 ${reports.total} 份，${reports.graded} 份已评分`
              : reports.hasUpload
                ? "已上传文件，等待提取正文"
                : "批量上传报告或压缩包"
          }
          trailing={<Badge tone={reports.total ? "ok" : ""}>{reports.total ? "已就绪" : "待上传"}</Badge>}
          chevron
        />
        <ListRow
          icon="results"
          to="/app/results"
          title="评分与终审"
          sub={
            reports.graded
              ? `已终审 ${approved} 份，剩 ${unapproved} 份待终审`
              : "逐份判级、改等级、写评语，终审后进入案例库"
          }
          value={`${reports.graded}/${reports.total || 0}`}
          chevron
        />
      </Group>

      {boot.agreement ? (
        <Group title="与教师真值的一致性" note={`${boot.agreement.n} 组对照`}>
          <div className="list-row" style={{ gap: 12 }}>
            <div className="grow kv">
              <div>
                <div className="kv-key">Cohen's κ</div>
                <div className="t-title-3 tnum">{metric(boot.agreement.cohen_kappa)}</div>
              </div>
              <div>
                <div className="kv-key">二次加权 κ</div>
                <div className="t-title-3 tnum">{metric(boot.agreement.weighted_kappa)}</div>
              </div>
              <div>
                <div className="kv-key">Krippendorff's α</div>
                <div className="t-title-3 tnum">{metric(boot.agreement.krippendorff_alpha)}</div>
              </div>
            </div>
            <LinkButton to="/app/results" size="sm">
              明细
            </LinkButton>
          </div>
        </Group>
      ) : null}

      {!rubric.count ? (
        <div style={{ marginBottom: 22 }}>
          <Banner tone="accent" icon="info">
            还没有评分细则。上传评分标准并生成细则后，「开始评分」才会启用。
          </Banner>
        </div>
      ) : null}

      {rubric.count && rubric.confirmed === false ? (
        <div style={{ marginBottom: 22 }}>
          <Banner tone="warn" icon="alert">
            评分细则还没确认：先到「评分细则」用 1–5 份样本校准，确认后才能开始评分。
          </Banner>
        </div>
      ) : null}

      <Group
        title="课程"
        note={`${boot.sessions.length} 门 · 数据按课程隔离`}
        footer="删除课程会移除该课程的本地产物（细则、报告、评分、向量库），不可撤销。"
      >
        {boot.sessions.map((session) => {
          const active = session.id === boot.session.id;
          return (
            <ListRow
              key={session.id}
              title={session.name}
              sub={session.id}
              onClick={active ? undefined : () => switchSession(session.id)}
              trailing={
                active ? (
                  <Badge tone="accent">当前</Badge>
                ) : (
                  <span className="btn btn-sm">切换</span>
                )
              }
            />
          );
        })}
        <div className="list-row">
          <Button
            variant="destructive"
            icon="trash"
            disabled={boot.sessions.length <= 1}
            onClick={() => setConfirm(true)}
          >
            删除当前课程
          </Button>
        </div>
      </Group>

      <Sheet
        open={confirm}
        title={`删除「${boot.session.name}」？`}
        text="该课程的细则、报告、评分结果与向量库会一并删除，无法恢复。"
        onClose={() => setConfirm(false)}
        footer={
          <>
            <Button onClick={() => setConfirm(false)}>取消</Button>
            <Button
              variant="filled"
              loading={busy}
              onClick={async () => {
                setBusy(true);
                const ok = await removeSession(boot.session.id);
                setBusy(false);
                if (ok) setConfirm(false);
              }}
            >
              确认删除
            </Button>
          </>
        }
      >
        <Field label="当前课程 ID" hint="删除后会自动切到剩余课程。">
          {(id) => <input id={id} className="input" value={boot.session.id} readOnly />}
        </Field>
      </Sheet>
    </>
  );
}
