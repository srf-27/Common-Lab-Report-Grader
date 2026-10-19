import { useEffect, useMemo, useState } from "react";
import { errorText, postForm } from "../lib/api";
import { studentText } from "../lib/format";
import { useData } from "../lib/hooks";
import { toast } from "../lib/toast";
import {
  Banner,
  Button,
  Dropzone,
  Empty,
  Group,
  IconButton,
  LinkButton,
  PageHead,
  Spinner,
  Stat,
} from "../ui";

export default function Roster() {
  const { data, error, loading, load } = useData("/api/roster");
  const [draft, setDraft] = useState({ headers: [], rows: [] });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!data?.roster) {
      setDraft({ headers: [], rows: [] });
      return;
    }
    setDraft({
      headers: data.roster.headers || [],
      rows: (data.roster.rows || []).map((row) => ({ ...row })),
    });
  }, [data]);

  const dirty = useMemo(
    () => Boolean(data?.roster) && JSON.stringify(draft) !== JSON.stringify(data.roster),
    [data, draft]
  );

  const upload = async (files) => {
    if (!files?.length) return;
    setBusy(true);
    try {
      await postForm("/roster/upload", { roster_file: files[0] });
      await load();
      toast("花名册已导入", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    try {
      await postForm("/roster/save", { data: JSON.stringify(draft) });
      await load();
      toast("花名册已保存", "ok");
    } catch (err) {
      toast(errorText(err), "danger");
    } finally {
      setBusy(false);
    }
  };

  const patchCell = (rowIndex, header, value) =>
    setDraft((prev) => ({
      ...prev,
      rows: prev.rows.map((row, index) => (index === rowIndex ? { ...row, [header]: value } : row)),
    }));

  const roster = data?.roster;
  const suspicious = data?.suspicious || [];
  const missing = data?.missing || [];

  return (
    <>
      <PageHead
        title="花名册"
        sub={
          roster
            ? `${roster.rows.length} 人 · 收到 ${data.reportCount} 份报告 · 缺交 ${missing.length} 人 · 可疑 ${suspicious.length} 份`
            : "上传名单后，报告里的学号姓名会与名册比对，自动列出缺交与可疑。"
        }
        actions={
          <Button variant="filled" icon="check" disabled={!dirty || busy} loading={busy} onClick={save}>
            保存名册
          </Button>
        }
      />

      {error ? (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="danger" icon="alert">
            {error}
          </Banner>
        </div>
      ) : null}

      {data?.mostlyUnmatched ? (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="warn" icon="alert">
            超过一半的报告在名册里找不到对应学生。多半是表头不对（需要「学号」或「姓名」列），或者报告里的学生信息没提取出来。
          </Banner>
        </div>
      ) : null}

      <div className="stat-grid" style={{ marginBottom: 18 }}>
        <Stat label="名册人数" value={roster?.rows.length || 0} suffix="人" />
        <Stat label="收到报告" value={data?.reportCount || 0} suffix="份" />
        <Stat label="缺交" value={missing.length} suffix="人" />
        <Stat label="可疑" value={suspicious.length} suffix="份" />
      </div>

      <Group
        title="导入名单"
        note=".xlsx / .csv"
        footer="第一行是表头；表头决定报告信息提取与导出列，至少包含「学号」或「姓名」。"
      >
        <Dropzone
          accept=".xlsx,.csv"
          title={roster ? "替换现有花名册" : "选择花名册"}
          hint={roster ? `当前表头：${roster.headers.join(" / ")}` : "第一行须为表头"}
          onFiles={upload}
          disabled={busy}
        />
      </Group>

      <Group
        title="名册内容"
        note={roster ? `${roster.headers.length} 列` : "尚未导入"}
        footer="直接改单元格，改完点右上角「保存名册」。"
      >
        {loading && !roster ? <Spinner label="读取名册…" /> : null}
        {roster ? (
          <div className="list-row" style={{ display: "block", padding: 0 }}>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: 40 }}>#</th>
                    {draft.headers.map((header) => (
                      <th key={header}>{header}</th>
                    ))}
                    <th style={{ width: 44 }} aria-label="操作" />
                  </tr>
                </thead>
                <tbody>
                  {draft.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      <td className="tnum c-secondary" style={{ fontSize: 12 }}>
                        {rowIndex + 1}
                      </td>
                      {draft.headers.map((header) => (
                        <td key={header} style={{ minWidth: 108 }}>
                          <input
                            className="cell-input"
                            aria-label={`第 ${rowIndex + 1} 行 ${header}`}
                            value={row[header] || ""}
                            onChange={(event) => patchCell(rowIndex, header, event.target.value)}
                          />
                        </td>
                      ))}
                      <td>
                        <IconButton
                          icon="trash"
                          label="删除这一行"
                          onClick={() =>
                            setDraft((prev) => ({
                              ...prev,
                              rows: prev.rows.filter((_, index) => index !== rowIndex),
                            }))
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : !loading ? (
          <div style={{ padding: 16 }}>
            <Empty icon="roster" title="还没有花名册" text="导入名单后，缺交名单与被标记人员 Excel 才会准确。" />
          </div>
        ) : null}
        {roster ? (
          <div className="list-row">
            <Button
              size="sm"
              icon="plus"
              onClick={() =>
                setDraft((prev) => ({
                  ...prev,
                  rows: [...prev.rows, Object.fromEntries(prev.headers.map((h) => [h, ""]))],
                }))
              }
            >
              新增一行
            </Button>
          </div>
        ) : null}
      </Group>

      {suspicious.length ? (
        <Group title="可疑报告" note={`${suspicious.length} 份`}>
          {suspicious.map((item) => (
            <div className="list-row" key={item.report_id}>
              <span className="row-main">
                <span className="row-title" style={{ display: "block" }}>
                  {studentText(item.student, roster?.headers)}
                </span>
                <span className="row-sub" style={{ display: "block" }}>
                  {item.report_id} · {item.reason}
                </span>
              </span>
              <LinkButton
                to={`/app/report/${encodeURIComponent(item.report_id)}`}
                size="sm"
                icon="pen"
              >
                修正
              </LinkButton>
            </div>
          ))}
        </Group>
      ) : null}

      {missing.length ? (
        <Group title="缺交名单" note={`${missing.length} 人`}>
          <div className="list-row" style={{ display: "block", padding: 0 }}>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    {(roster?.headers || []).map((header) => (
                      <th key={header}>{header}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {missing.map((row, index) => (
                    <tr key={index}>
                      {(roster?.headers || []).map((header) => (
                        <td key={header}>{row[header] || "—"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Group>
      ) : null}

      {dirty ? (
        <div className="action-bar">
          <span className="t-subhead grow">名册有未保存的修改</span>
          <Button onClick={() => setDraft({ headers: data.roster.headers, rows: data.roster.rows.map((r) => ({ ...r })) })}>
            放弃
          </Button>
          <Button variant="filled" loading={busy} onClick={save}>
            保存名册
          </Button>
        </div>
      ) : null}
    </>
  );
}
