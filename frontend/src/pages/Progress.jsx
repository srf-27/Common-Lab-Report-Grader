import { useCallback, useState } from "react";
import { errorText, getJSON, postEmpty } from "../lib/api";
import { usePoll } from "../lib/hooks";
import { toast } from "../lib/toast";
import {
  Badge,
  Banner,
  Button,
  Empty,
  Group,
  LinkButton,
  PageHead,
  Progress,
  Spinner,
} from "../ui";

export default function GradingProgress() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");

  const tick = useCallback(async () => {
    try {
      setStatus(await getJSON("/grading_status"));
      setError("");
    } catch (err) {
      setError(errorText(err));
    }
  }, []);

  usePoll(tick, 1200, !status || status.phase === "running");

  const total = status?.total || 0;
  const done = status?.done || 0;
  const percent = total ? Math.round((done / total) * 100) : status?.phase === "done" ? 100 : 0;
  const running = status?.phase === "running";

  return (
    <>
      <PageHead
        title={running || !status ? "评分进行中" : "评分进度"}
        sub={
          running
            ? "逐份判级，每份都有安全与相似度检查；可以离开本页，评分在后台继续。"
            : "评分任务的实时状态。"
        }
        actions={
          running ? (
            <Button
              variant="destructive"
              icon="pause"
              onClick={() =>
                postEmpty("/grading_cancel")
                  .then(() => toast("已请求取消，当前这份评完就停"))
                  .catch((err) => toast(errorText(err), "danger"))
              }
            >
              取消评分
            </Button>
          ) : null
        }
      />

      {error ? <Banner tone="danger" icon="alert">{error}</Banner> : null}

      {!status ? <Spinner label="读取评分状态…" /> : null}

      {status?.phase === "idle" ? (
        <Empty
          icon="select"
          title="当前没有评分任务"
          text="在「选择评分」里勾选报告后开始。"
          action={
            <LinkButton to="/app/select" variant="filled" icon="select">
              选择报告
            </LinkButton>
          }
        />
      ) : null}

      {status && status.phase !== "idle" ? (
        <Group
          title={
            status.phase === "done"
              ? "评分完成"
              : status.phase === "cancelled"
                ? "已取消"
                : status.phase === "error"
                  ? "评分出错"
                  : "正在评分"
          }
          note={status.message || (status.workers > 1 ? `并发 ${status.workers} 路` : "")}
          actions={<Badge tone={status.phase === "done" ? "ok" : status.phase === "error" ? "danger" : ""}>{done}/{total || "—"}</Badge>}
          footer="默认 3 路并行，单份通常 10–40 秒；模型失败的报告会标为「模型失败」并可单独重评，不会伪造分数。"
        >
          <div className="list-row" style={{ display: "block", paddingTop: 16, paddingBottom: 16 }}>
            <Progress value={percent} tone={status.phase === "error" ? "danger" : undefined} />
            <div className="spread" style={{ marginTop: 12 }}>
              <div style={{ minWidth: 0 }}>
                <div className="t-headline truncate">
                  {running
                    ? status.current || "准备中…"
                    : status.phase === "done"
                      ? "全部完成"
                      : status.message || status.phase}
                </div>
                <div className="t-footnote c-secondary" style={{ marginTop: 2 }}>
                  {running
                    ? `已完成 ${done} 份 / 共 ${total} 份`
                    : `已处理 ${done} 份`}
                </div>
              </div>
              <span className="t-title-3 tnum">{percent}%</span>
            </div>
          </div>
          <div className="list-row" style={{ gap: 8 }}>
            <LinkButton to="/app/results" variant="filled" icon="results">
              查看评分结果
            </LinkButton>
            <LinkButton to="/app/select" icon="select">
              继续选择
            </LinkButton>
          </div>
        </Group>
      ) : null}
    </>
  );
}
