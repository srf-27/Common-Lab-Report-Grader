import { useState } from "react";
import { errorText, postForm } from "../lib/api";
import { LEVEL_LABEL, statusMeta, timeText, totalScore } from "../lib/format";
import { useData } from "../lib/hooks";
import { Prose } from "../lib/markdown";
import { toast } from "../lib/toast";
import {
  Badge,
  Banner,
  Button,
  Empty,
  Field,
  Group,
  Icon,
  LevelBadge,
  LinkButton,
  PageHead,
  Sheet,
  Spinner,
} from "../ui";

export default function ReportDetail({ filename }) {
  const { data, error, loading, load } = useData(`/api/report/${encodeURIComponent(filename)}`);
  const [editing, setEditing] = useState(false);
  const [student, setStudent] = useState({});
  const [busy, setBusy] = useState(false);

  const fields = data?.fields || [];
  const result = data?.result;
  const meta = statusMeta(result?.status);
  const total = totalScore(result);
  const blocks = data?.blocks || [];
  const graded = result?.status === "graded";
  const studentName =
    data?.student?.["姓名"] || Object.values(data?.student || {}).find((value) => value);

  const saveStudent = async () => {
    setBusy(true);
    try {
      const payload = { next: `/app/report/${encodeURIComponent(filename)}` };
      fields.forEach((field) => {
        payload[`student::${field}`] = student[field] || "";
      });
      await postForm(`/update_student/${encodeURIComponent(filename)}`, payload);
      await load();
      toast("学生信息已更新", "ok");
      setEditing(false);
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHead
        title={studentName || filename}
        sub={studentName ? filename : `${filename} · 未识别学生，可补全学生信息`}
        actions={
          <>
            <Button
              icon="pen"
              onClick={() => {
                setStudent({ ...(data?.student || {}) });
                setEditing(true);
              }}
            >
              学生信息
            </Button>
            {data?.hasOriginal ? (
              <a
                className="btn btn-tinted"
                href={`/report_original/${encodeURIComponent(filename)}`}
                target="_blank"
                rel="noreferrer"
              >
                <Icon name="external" size={15} />
                原文
              </a>
            ) : (
              <Button icon="external" disabled title="原始文件已不在工作目录">
                原文
              </Button>
            )}
          </>
        }
      />

      {error ? (
        <Banner tone="danger" icon="alert">
          {error}
        </Banner>
      ) : null}

      {loading && !data ? <Spinner label="读取报告…" /> : null}

      {data ? (
        <div className="split">
          <Group title="维度切分" note={`${blocks.length} 个维度块`}>
            {!graded ? (
              <div style={{ marginBottom: 12 }}>
                <Banner icon="info">
                  尚未评分——评分时模型会把正文段落归入各维度，届时此处显示挂载结果；修改过细则会清空已有结果，需重新评分。
                </Banner>
              </div>
            ) : null}
            {blocks.length ? (
              blocks.map((block, index) => (
                <div key={`${block.criterion}-${index}`} className="list-row" style={{ display: "block" }}>
                  <div className="spread" style={{ marginBottom: 8 }}>
                    <span className="row" style={{ minWidth: 0, gap: 6 }}>
                      <span className="t-headline truncate">{block.criterion}</span>
                      {block.weight !== null && block.weight !== undefined ? (
                        <span className="row-sub" style={{ margin: 0 }}>
                          {block.weight}%
                        </span>
                      ) : null}
                    </span>
                    <span className="row" style={{ gap: 8 }}>
                      <span className="t-caption c-secondary">
                        {block.chunks?.length || 0} 段 · {block.images?.length || 0} 图
                      </span>
                      {block.score?.external ? (
                        <Badge tone="ok">成绩单 {Math.round(Number(block.score.score))}</Badge>
                      ) : block.score?.level ? (
                        <LevelBadge
                          level={block.score.level}
                          title={`${block.score.level} ${LEVEL_LABEL[block.score.level] || ""}`}
                        />
                      ) : null}
                    </span>
                  </div>

                  {block.chunks?.length ? (
                    block.chunks.map((chunk, chunkIndex) => <Prose key={chunkIndex} text={chunk} />)
                  ) : (
                    <p className="t-subhead c-secondary">该维度没有挂载正文段落。</p>
                  )}

                  {block.images?.length ? (
                    <div className="figures">
                      {block.images.map((image) => (
                        <a
                          key={image.filename}
                          className="figure"
                          href={`/report_image/${encodeURIComponent(filename)}/${encodeURIComponent(
                            image.filename
                          )}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <img
                            src={`/report_image/${encodeURIComponent(filename)}/${encodeURIComponent(
                              image.filename
                            )}`}
                            alt={image.filename}
                            loading="lazy"
                          />
                          <figcaption>
                            {image.page ? `P${image.page} · ` : ""}
                            {image.filename}
                          </figcaption>
                        </a>
                      ))}
                    </div>
                  ) : null}

                  {block.score ? (
                    <div style={{ marginTop: 10 }}>
                      <div className="row-wrap" style={{ gap: 6, marginBottom: 6 }}>
                        <Badge tone={block.score.teacher_adjusted ? "warn" : "ok"}>
                          {block.score.external
                            ? `成绩单 ${Math.round(Number(block.score.score))}`
                            : `${block.score.level} · ${LEVEL_LABEL[block.score.level] || ""}`}
                        </Badge>
                        {block.score.external ? <Badge outline>已计入总分</Badge> : null}
                        {block.score.ai_level ? <Badge outline>AI 原判 {block.score.ai_level}</Badge> : null}
                        {block.score.teacher_adjusted ? <Badge tone="warn">教师已改</Badge> : null}
                      </div>
                      {block.score.evidence ? (
                        <div className="quote">原文依据：{block.score.evidence}</div>
                      ) : null}
                      {block.score.reasoning ? (
                        <p className="t-footnote c-secondary" style={{ marginTop: 6 }}>
                          {block.score.reasoning}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ))
            ) : (
              <div style={{ padding: 16 }}>
                <Empty title="没有可显示的正文" text="报告可能未提取成功，或正文为空。" />
              </div>
            )}
          </Group>

          <div className="stack side-sticky">
            <Group title="评分" note={result ? meta.label : "未评分"}>
              {graded ? (
                <div className="list-row" style={{ display: "block" }}>
                  <div className="score-hero">
                    {total === null ? "—" : total}
                    <small>/ 100</small>
                  </div>
                  <div className="kv" style={{ marginTop: 12 }}>
                    <div>
                      <div className="kv-key">评分时间</div>
                      <div className="kv-val">{timeText(result.graded_at)}</div>
                    </div>
                  </div>
                  <div style={{ borderTop: "1px solid var(--separator)", margin: "12px 0" }} />
                  <div className="stack" style={{ gap: 8 }}>
                    {Object.entries(result.grading.scores || {}).map(([name, score]) => (
                      <div key={name} className="dim-row">
                        <span className="t-subhead truncate">{name}</span>
                        {score.external ? (
                          <Badge tone="ok">成绩单 {Math.round(Number(score.score))}</Badge>
                        ) : (
                          <LevelBadge level={score.level} />
                        )}
                      </div>
                    ))}
                  </div>
                  {result.similarity_warnings?.length ? (
                    <div style={{ marginTop: 12 }}>
                      <Banner tone="warn" icon="alert">
                        {result.similarity_warnings.map((warning, index) => (
                          <div key={index}>
                            与 <strong>{warning.matched_id}</strong> 相似度{" "}
                            {Math.round(warning.similarity * 1000) / 10}%
                            {warning.level === "rejected" ? "（高度重复）" : ""}
                          </div>
                        ))}
                      </Banner>
                    </div>
                  ) : null}
                  {result.warnings?.length ? (
                    <p className="t-footnote c-secondary" style={{ marginTop: 10 }}>
                      {result.warnings.join("；")}
                    </p>
                  ) : null}
                  <div style={{ marginTop: 12 }}>
                    <LinkButton to="/app/results" variant="tinted" size="sm" icon="results">
                      去评分结果修改
                    </LinkButton>
                  </div>
                </div>
              ) : result ? (
                <div className="list-row">
                  <Banner tone={meta.tone === "danger" ? "danger" : "warn"} icon="alert">
                    {meta.label}
                    {result.error ? `：${result.error}` : ""}
                    {result.injection_details?.evidence ? `：${result.injection_details.evidence}` : ""}
                  </Banner>
                </div>
              ) : (
                <div style={{ padding: 16 }}>
                  <Empty
                    icon="select"
                    title="尚未评分"
                    text="在「选择评分」里勾选这份报告，评分完成后这里显示逐维度结果。"
                    action={
                      <LinkButton to="/app/select" variant="tinted" size="sm" icon="play">
                        去评分
                      </LinkButton>
                    }
                  />
                </div>
              )}
            </Group>

            <Group title="学生信息">
              <div className="list-row" style={{ display: "block" }}>
                <div className="kv">
                  {(fields.length ? fields : ["姓名", "学号"]).map((field) => (
                    <div key={field}>
                      <div className="kv-key">{field}</div>
                      <div className="kv-val">{data.student?.[field] || "—"}</div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 12 }}>
                  <Button
                    size="sm"
                    icon="pen"
                    onClick={() => {
                      setStudent({ ...(data.student || {}) });
                      setEditing(true);
                    }}
                  >
                    修改
                  </Button>
                </div>
              </div>
            </Group>
          </div>
        </div>
      ) : null}

      <Sheet
        open={editing}
        title="学生信息"
        text="学号与姓名要和花名册一致，否则会被列为可疑报告。"
        onClose={() => setEditing(false)}
        footer={
          <>
            <Button onClick={() => setEditing(false)}>取消</Button>
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
