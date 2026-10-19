import { useMemo, useState } from "react";
import { errorText, postForm, postJSON } from "../lib/api";
import { LEVEL_LABEL } from "../lib/format";
import { useData } from "../lib/hooks";
import { Prose } from "../lib/markdown";
import { toast } from "../lib/toast";
import {
  Badge,
  Banner,
  Button,
  Disclosure,
  Dropzone,
  Field,
  Group,
  LevelBadge,
  LevelPicker,
  LinkButton,
  PageHead,
  Spinner,
} from "../ui";

export default function Calibration() {
  const { data, error, loading, load } = useData("/api/calibration");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [levels, setLevels] = useState({});
  const [reasons, setReasons] = useState({});
  const [outcome, setOutcome] = useState(null);

  const rows = data?.rows || [];
  const filled = useMemo(() => Object.values(levels).filter(Boolean).length, [levels]);

  const upload = async () => {
    if (!file) return toast("请先选择一份教师已判的示例报告", "danger");
    setBusy(true);
    try {
      await postForm("/calibrate_upload", { calibration_report: file });
      await load();
      setFile(null);
      setOutcome(null);
      toast("已解析示例报告，请填写教师判级", "ok");
    } catch (err) {
      toast(`${errorText(err)}（解析失败通常是文件不可读或格式不支持）`, "danger");
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (!filled) return toast("至少给一个维度填上教师判级", "danger");
    setBusy(true);
    try {
      setOutcome(await postJSON("/api/calibration/submit", { levels, reasons }));
      toast("对比完成", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  const analysis = outcome?.analysis || {};
  const disagreements = analysis.disagreements || [];
  const aiScores = outcome?.aiGrading?.scores || {};

  return (
    <>
      <PageHead
        title="评分校准"
        sub="上传一份教师已经判过的报告，对比 AI 与教师的分歧，据此改细则的等级边界。"
        actions={
          <>
            <LinkButton to="/app/rubric" icon="rubric">
              评分细则
            </LinkButton>
            {data?.ready ? (
              <Button
                variant="filled"
                icon="check"
                disabled={!filled || busy}
                loading={busy}
                onClick={submit}
              >
                对比（{filled}）
              </Button>
            ) : null}
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

      {loading && !data ? <Spinner label="读取校准状态…" /> : null}

      {data && !data.ready ? (
        <Group title="示例报告" note="教师已判过的一份" footer="上传后会先解析正文并按维度挂载段落，再请你填写教师判级。">
          <Dropzone
            accept=".pdf,.docx,.doc,.md,.txt"
            title={file ? file.name : "选择示例报告"}
            hint="建议选一份教师判级与 AI 分歧明显的报告"
            onFiles={(files) => setFile(files[0])}
            disabled={busy}
          />
          <div className="list-row" style={{ gap: 8 }}>
            <Button
              variant="filled"
              icon="upload"
              disabled={!file || busy}
              loading={busy}
              onClick={upload}
            >
              解析示例
            </Button>
            <span className="row-sub" style={{ marginLeft: "auto" }}>
              尚未解析示例报告
            </span>
          </div>
        </Group>
      ) : null}

      {data?.ready ? (
        <>
          <Group
            title="填写教师判级"
            note={data.filename}
            footer="每行的等级可再次点击取消；理由会一并交给模型做对比。"
          >
            {rows.map((row) => (
              <Disclosure
                key={row.criterion.name}
                summary={
                  <span className="row" style={{ minWidth: 0, gap: 8 }}>
                    <span className="row-title">{row.criterion.name}</span>
                    <span className="row-sub" style={{ margin: 0 }}>
                      {row.criterion.weight}%
                    </span>
                    <span className="t-caption c-secondary">{row.paragraphs.length} 段</span>
                  </span>
                }
                meta={
                  <LevelPicker
                    allowEmpty
                    label={`${row.criterion.name} 教师判级`}
                    value={levels[row.criterion.name] || ""}
                    onChange={(level) =>
                      setLevels((prev) => ({ ...prev, [row.criterion.name]: level }))
                    }
                  />
                }
              >
                <div className="stack">
                  {row.paragraphs.length ? (
                    row.paragraphs.map((paragraph, index) => <Prose key={index} text={paragraph} />)
                  ) : (
                    <p className="t-subhead c-secondary">这份报告在该维度没有提取到对应段落。</p>
                  )}
                  <Field label="教师理由" hint="写清为什么给这一级，对比时会一并交给模型">
                    {(id) => (
                      <textarea
                        id={id}
                        className="textarea"
                        value={reasons[row.criterion.name] || ""}
                        onChange={(event) =>
                          setReasons((prev) => ({
                            ...prev,
                            [row.criterion.name]: event.target.value,
                          }))
                        }
                      />
                    )}
                  </Field>
                </div>
              </Disclosure>
            ))}
          </Group>

          {data.rest?.length ? (
            <Group title="未挂载内容" note={`${data.rest.length} 段`}>
              <div className="list-row" style={{ display: "block" }}>
                {data.rest.map((paragraph, index) => (
                  <Prose key={index} text={paragraph} />
                ))}
              </div>
            </Group>
          ) : null}

          <Group title="替换示例报告" footer="重新解析会丢掉当前已填的教师判级。">
            <Dropzone
              accept=".pdf,.docx,.doc,.md,.txt"
              title={file ? file.name : "换一份示例报告"}
              hint="PDF / DOCX / MD / TXT"
              onFiles={(files) => setFile(files[0])}
              disabled={busy}
            />
            <div className="list-row">
              <Button icon="upload" disabled={!file || busy} loading={busy} onClick={upload}>
                重新解析
              </Button>
            </div>
          </Group>
        </>
      ) : null}

      {outcome ? (
        <Group
          title="对比结果"
          note={analysis.agreements?.length ? `一致：${analysis.agreements.join("、")}` : undefined}
          actions={<Button size="sm" onClick={() => setOutcome(null)}>收起</Button>}
        >
          <div className="list-row" style={{ display: "block", padding: 0 }}>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>维度</th>
                    <th>AI</th>
                    <th>教师</th>
                    <th>AI 理由</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(aiScores).map(([name, score]) => {
                    const same = levels[name] && levels[name] === score.level;
                    return (
                      <tr key={name}>
                        <td style={{ maxWidth: 180 }}>{name}</td>
                        <td>
                          <span className="row" style={{ gap: 5 }}>
                            <LevelBadge level={score.level} />
                            <span className="t-caption c-secondary">
                              {LEVEL_LABEL[score.level] || ""}
                            </span>
                          </span>
                        </td>
                        <td>
                          {levels[name] ? (
                            <span className="row" style={{ gap: 5 }}>
                              <LevelBadge level={levels[name]} />
                              {same ? (
                                <Badge tone="ok">一致</Badge>
                              ) : (
                                <Badge tone="warn">分歧</Badge>
                              )}
                            </span>
                          ) : (
                            <span className="c-secondary">未填</span>
                          )}
                        </td>
                        <td className="c-secondary" style={{ fontSize: 13, maxWidth: 320 }}>
                          {score.reasoning || "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {disagreements.length ? (
            <div className="list-row" style={{ display: "block" }}>
              <div className="t-headline" style={{ marginBottom: 8 }}>
                分歧与修订建议
              </div>
              <div className="stack" style={{ gap: 10 }}>
                {disagreements.map((item, index) => (
                  <div key={index} className="banner">
                    <div>
                      <div className="row-wrap" style={{ gap: 6, marginBottom: 4 }}>
                        <strong>{item.criterion}</strong>
                        <Badge outline>教师 {item.teacher_score}</Badge>
                        <Badge outline>AI {item.ai_score}</Badge>
                      </div>
                      <div className="t-subhead">{item.reason}</div>
                      {item.suggested_rubric_adjustment ? (
                        <div className="quote" style={{ marginTop: 6 }}>
                          建议：{item.suggested_rubric_adjustment}
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {analysis.suggested_rubric_revisions ? (
            <div className="list-row" style={{ display: "block" }}>
              <div className="t-headline" style={{ marginBottom: 8 }}>
                建议的细则修订
              </div>
              <pre
                className="prose"
                style={{
                  whiteSpace: "pre-wrap",
                  background: "var(--fill)",
                  borderRadius: 10,
                  padding: 12,
                  fontSize: 12.5,
                }}
              >
                {analysis.suggested_rubric_revisions}
              </pre>
            </div>
          ) : null}

          <div className="list-row">
            <LinkButton to="/app/rubric" size="sm" icon="rubric">
              按建议改细则
            </LinkButton>
          </div>
        </Group>
      ) : null}
    </>
  );
}
