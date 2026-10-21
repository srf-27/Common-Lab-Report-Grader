import { useCallback, useEffect, useState } from "react";
import { errorText, getJSON } from "../lib/api";
import { useData } from "../lib/hooks";
import { Prose } from "../lib/markdown";
import {
  Badge,
  Banner,
  Button,
  Disclosure,
  Empty,
  Group,
  ListRow,
  PageHead,
  Spinner,
  Stat,
} from "../ui";

const PAGE_SIZE = 20;

const fmtCount = (value) => (Number(value) || 0).toLocaleString("zh-CN");

const metaText = (value) => {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
};

function VectorList() {
  const { data, error, loading, load } = useData("/api/vector");
  const collections = data?.collections || [];

  return (
    <>
      <PageHead
        title="向量库"
        sub="当前课程的 Chroma collection；只读预览，不会改动数据"
        actions={<Button icon="refresh" onClick={load}>刷新</Button>}
      />

      {error ? (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="danger" icon="alert" actions={<Button size="sm" onClick={load}>重试</Button>}>
            {error}
          </Banner>
        </div>
      ) : null}

      {loading && !data ? <Spinner label="读取向量库…" /> : null}

      {!loading && !error && data && collections.length === 0 ? (
        <Empty
          icon="database"
          title="还没有 collection"
          text="完成一次评分或终审后，案例库与维度参考库会自动出现在这里。"
        />
      ) : null}

      {collections.length ? (
        <Group title="Collections" note={`${collections.length} 个`} footer="全文库用于相似度与范例检索；维度库按维度保存已终审段落，评分时作为同维度参考。">
          {collections.map((item) => (
            <ListRow
              key={item.name}
              to={`/app/vector/${encodeURIComponent(item.name)}`}
              icon="database"
              title={item.label || item.name}
              sub={item.label && item.label !== item.name ? `${item.kind} · ${item.name}` : item.kind}
              value={`${fmtCount(item.count)} 条`}
              trailing={item.dimension ? <Badge outline>{item.dimension} 维</Badge> : null}
              chevron
            />
          ))}
        </Group>
      ) : null}
    </>
  );
}

function VectorDetail({ name }) {
  const [offset, setOffset] = useState(0);
  const [nonce, setNonce] = useState(0);
  const [state, setState] = useState({ data: null, error: "", loading: true });

  useEffect(() => {
    let alive = true;
    setState((prev) => ({ ...prev, loading: true, error: "" }));
    getJSON(`/api/vector/${encodeURIComponent(name)}?offset=${offset}&limit=${PAGE_SIZE}`)
      .then((data) => {
        if (alive) setState({ data, error: "", loading: false });
      })
      .catch((err) => {
        if (alive) setState({ data: null, error: errorText(err), loading: false });
      });
    return () => {
      alive = false;
    };
  }, [name, offset, nonce]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);
  const { data, error, loading } = state;
  const total = data?.total || 0;
  const items = data?.items || [];
  const start = total ? offset + 1 : 0;
  const end = Math.min(offset + items.length, total);
  const metaEntries = Object.entries(data?.metadata || {});

  return (
    <>
      <PageHead
        title={data?.label || name}
        sub={data?.label && data.label !== name ? name : "Collection 详情"}
        crumbs={[
          { to: "/app/vector", label: "向量库" },
          { label: data?.label || name },
        ]}
        actions={<Button icon="refresh" onClick={reload} loading={loading}>刷新</Button>}
      />

      {error ? (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="danger" icon="alert" actions={<Button size="sm" onClick={reload}>重试</Button>}>
            {error}
          </Banner>
        </div>
      ) : null}

      {loading && !data ? <Spinner label="读取 collection…" /> : null}

      {data ? (
        <>
          <div className="stat-grid" style={{ marginBottom: 18 }}>
            <Stat label="数据条数" value={fmtCount(total)} suffix="条" />
            <Stat label="向量维度" value={data.dimension || "—"} />
            <Stat label="类型" value={data.kind || "—"} />
          </div>

          <Group title="元数据" note={`${metaEntries.length} 项`}>
            {metaEntries.length ? (
              metaEntries.map(([key, value]) => (
                <div className="list-row" key={key} style={{ alignItems: "flex-start" }}>
                  <span className="row-main">
                    <span className="row-title" style={{ display: "block" }}>{key}</span>
                  </span>
                  <span className="row-value" style={{ maxWidth: "62%", textAlign: "right" }}>
                    <span className="vector-inline">{metaText(value)}</span>
                  </span>
                </div>
              ))
            ) : (
              <div className="list-row"><span className="row-sub" style={{ margin: 0 }}>没有元数据</span></div>
            )}
          </Group>

          <Group
            title="数据条目"
            note={total ? `${start}–${end} / 共 ${fmtCount(total)} 条` : "0 条"}
            footer="正文最多展示前 4000 字符；向量只展示前 8 维，完整向量保留在库内。"
          >
            {!items.length ? (
              <Empty icon="database" title="这个 collection 还没有数据" text="评分或终审后会自动写入。" />
            ) : (
              items.map((item) => (
                <Disclosure
                  key={item.id}
                  summary={
                    <span className="row" style={{ minWidth: 0, gap: 8 }}>
                      <span className="row-title truncate" style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }}>
                        {item.id}
                      </span>
                      <Badge>{fmtCount(item.docChars)} 字符</Badge>
                    </span>
                  }
                  meta={
                    <span className="row-sub" style={{ margin: 0 }}>
                      {item.dimension ?? data.dimension ?? "—"} 维
                    </span>
                  }
                >
                  <div className="stack" style={{ gap: 14 }}>
                    <div>
                      <div className="field-label">元数据</div>
                      <pre className="vector-meta">{JSON.stringify(item.metadata || {}, null, 2)}</pre>
                    </div>
                    <div>
                      <div className="field-label">
                        正文{item.truncated ? `（前 4000 字符 / 共 ${fmtCount(item.docChars)}）` : ""}
                      </div>
                      {item.document ? (
                        <div className="quote" style={{ maxHeight: 420, overflow: "auto" }}>
                          <Prose text={item.document} />
                        </div>
                      ) : (
                        <span className="row-sub">（无文本）</span>
                      )}
                    </div>
                    <div>
                      <div className="field-label">
                        向量预览（前 8 维 / 共 {item.dimension ?? data.dimension ?? "—"} 维）
                      </div>
                      <pre className="vector-meta">
                        {(item.embeddingPreview || []).join(", ") || "（没有向量）"}
                      </pre>
                    </div>
                  </div>
                </Disclosure>
              ))
            )}
          </Group>

          {total > PAGE_SIZE ? (
            <div className="row" style={{ justifyContent: "space-between", gap: 12, marginTop: 14 }}>
              <span className="row-sub" style={{ margin: 0 }}>
                {start}–{end} / 共 {fmtCount(total)} 条
              </span>
              <div className="row" style={{ gap: 8 }}>
                <Button disabled={offset <= 0 || loading} onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}>
                  上一页
                </Button>
                <Button disabled={end >= total || loading} onClick={() => setOffset((value) => value + PAGE_SIZE)}>
                  下一页
                </Button>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </>
  );
}

export default function VectorStore({ name }) {
  return name ? <VectorDetail key={name} name={name} /> : <VectorList />;
}
