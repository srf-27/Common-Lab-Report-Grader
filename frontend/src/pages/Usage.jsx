/* 版式与配色参照 cc-switch（MIT）的用量统计页：KPI 英雄区 + 平滑面积趋势图 + 明细表 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { getJSON, postEmpty } from "../lib/api";
import { useData } from "../lib/hooks";
import { Badge, Empty, Icon, IconButton, Spinner, Switch } from "../ui";

const INTERVALS = [
  [30, "30 秒"],
  [60, "1 分钟"],
  [300, "5 分钟"],
  [900, "15 分钟"],
];

const pref = (key, fallback) => {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
};

const savePref = (key, value) => {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* 隐私模式下忽略 */
  }
};

const RANGES = [
  ["1", "今天"],
  ["7", "7 天"],
  ["30", "30 天"],
  ["0", "全部"],
];

const SERIES = [
  { key: "cost", label: "成本", color: "#7c5cff", axis: "money" },
  { key: "cached", label: "缓存命中", color: "#ff5c8a", axis: "token", area: true, dashed: true },
  { key: "input", label: "输入", color: "#3b82f6", axis: "token" },
  { key: "output", label: "输出", color: "#22c55e", axis: "token" },
];

const fmtInt = (value) => (Number(value) || 0).toLocaleString("zh-CN");

const fmtCN = (value) => {
  const n = Number(value) || 0;
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)} 亿`;
  if (n >= 1e4) return `${(n / 1e4).toFixed(1)} 万`;
  return fmtInt(n);
};

const fmtAxis = (value) => {
  const n = Number(value) || 0;
  if (n >= 1e8) return `${(n / 1e8).toFixed(1)}亿`;
  if (n >= 1e4) return `${(n / 1e4).toFixed(0)}万`;
  return fmtInt(n);
};

const money = (value, digits = 2) => {
  const n = Number(value) || 0;
  if (!n) return "0.00";
  return n < 0.01 ? n.toFixed(4) : n.toFixed(digits);
};

const clock = (ts) => {
  const d = new Date(ts * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

const dayLabel = (ts) => {
  const d = new Date(ts * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())}`;
};

const tickLabel = (ts, days) => (days <= 1 ? clock(ts) : dayLabel(ts));

/* 版式沿用 cc-switch：平滑面积 + 双轴（左 token / 右 ¥），不画柱状图 */
/* 单调三次插值（Fritsch–Carlson）：曲线平滑但不会过冲到 0 以下 */
function smoothPath(points) {
  if (!points.length) return "";
  if (points.length === 1) return `M${points[0][0]},${points[0][1]}`;
  const n = points.length;
  const dx = [];
  const slope = [];
  for (let i = 0; i < n - 1; i += 1) {
    dx[i] = points[i + 1][0] - points[i][0] || 0.0001;
    slope[i] = (points[i + 1][1] - points[i][1]) / dx[i];
  }
  const m = [slope[0]];
  for (let i = 1; i < n - 1; i += 1) {
    m[i] = slope[i - 1] * slope[i] <= 0 ? 0 : (slope[i - 1] + slope[i]) / 2;
  }
  m[n - 1] = slope[n - 2];
  for (let i = 0; i < n - 1; i += 1) {
    if (slope[i] === 0) {
      m[i] = 0;
      m[i + 1] = 0;
      continue;
    }
    const a = m[i] / slope[i];
    const b = m[i + 1] / slope[i];
    const s = a * a + b * b;
    if (s > 9) {
      const t = 3 / Math.sqrt(s);
      m[i] = t * a * slope[i];
      m[i + 1] = t * b * slope[i];
    }
  }
  let d = `M${points[0][0]},${points[0][1]}`;
  for (let i = 0; i < n - 1; i += 1) {
    const h = dx[i] / 3;
    d += ` C${(points[i][0] + h).toFixed(1)},${(points[i][1] + m[i] * h).toFixed(1)}`
      + ` ${(points[i + 1][0] - h).toFixed(1)},${(points[i + 1][1] - m[i + 1] * h).toFixed(1)}`
      + ` ${points[i + 1][0].toFixed(1)},${points[i + 1][1].toFixed(1)}`;
  }
  return d;
}

/* 时间轴补空：今天 24 个小时桶、多天逐个自然日，没调用的时段留 0 */
function buildSlots(buckets, days) {
  const midnight = (ts) => {
    const d = new Date(ts * 1000);
    d.setHours(0, 0, 0, 0);
    return Math.floor(d.getTime() / 1000);
  };
  const now = Math.floor(Date.now() / 1000);
  const span = days === 1 ? 3600 : 86400;
  let start;
  let count;
  if (days === 1) {
    start = midnight(now);
    count = 24;
  } else if (days > 1) {
    start = midnight(now) - (days - 1) * 86400;
    count = days;
  } else if (buckets.length) {
    start = midnight(buckets[0].t);
    count = Math.min(60, Math.floor((now - start) / 86400) + 1);
  } else {
    return [];
  }
  const slots = Array.from({ length: count }, (_, i) => ({
    t: start + i * span,
    cost: 0,
    i: 0,
    c: 0,
    o: 0,
    calls: 0,
  }));
  for (const bucket of buckets) {
    const index = Math.floor((bucket.t - start) / span);
    if (index >= 0 && index < slots.length) {
      slots[index].cost += bucket.cost || 0;
      slots[index].i += bucket.i || 0;
      slots[index].c += bucket.c || 0;
      slots[index].o += bucket.o || 0;
      slots[index].calls += bucket.calls || 0;
    }
  }
  return slots;
}

function Chart({ buckets, days, scale = 1 }) {
  const width = 920;
  const height = 300;
  const padL = 64;
  const padR = 64;
  const padT = 16;
  const padB = 30;
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;
  const [hover, setHover] = useState(null);

  const rows = useMemo(
    () =>
      buildSlots(buckets, days).map((slot) => ({
        t: slot.t,
        cost: slot.cost * scale,
        input: Math.max(0, slot.i - slot.c),
        cached: slot.c,
        output: slot.o,
        calls: slot.calls,
      })),
    [buckets, days, scale]
  );

  const niceStep = (max) => {
    const rough = max / 4 || 1;
    const pow = 10 ** Math.floor(Math.log10(rough));
    const unit = rough / pow;
    return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * pow;
  };

  const maxToken = Math.max(1, ...rows.map((r) => Math.max(r.input, r.cached, r.output)));
  const tokenStep = niceStep(maxToken);
  const tokenTop = Math.ceil(maxToken / tokenStep) * tokenStep;
  const tokenTicks = Array.from({ length: Math.round(tokenTop / tokenStep) + 1 }, (_, i) => i * tokenStep);

  const maxCost = Math.max(0.000001, ...rows.map((r) => r.cost));
  const costStep = niceStep(maxCost);
  const costTop = Math.ceil(maxCost / costStep) * costStep;
  const costTicks = Array.from({ length: Math.round(costTop / costStep) + 1 }, (_, i) => i * costStep);

  const step = rows.length > 1 ? innerW / (rows.length - 1) : 0;
  const x = (i) => (rows.length > 1 ? padL + i * step : padL + innerW / 2);
  const yToken = (v) => padT + innerH - (v / tokenTop) * innerH;
  const yCost = (v) => padT + innerH - (v / costTop) * innerH;

  // 平滑曲线在 0 附近会过冲：夹在绘图区内，避免线条钻到轴下面
  const clamp = (value) => Math.max(padT, Math.min(padT + innerH, value));
  const pathFor = (key) =>
    smoothPath(
      rows.map((row, i) => [x(i), clamp(key === "cost" ? yCost(row.cost) : yToken(row[key] || 0))])
    );

  const areaFor = (key) => {
    const line = pathFor(key);
    if (!line || !rows.length) return "";
    const bottom = padT + innerH;
    return `${line} L${x(rows.length - 1)},${bottom} L${x(0)},${bottom} Z`;
  };

  const labelEvery = Math.max(1, Math.ceil(rows.length / 8));

  return (
    <div className="u-chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="使用趋势"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(event) => {
          const box = event.currentTarget.getBoundingClientRect();
          const px = ((event.clientX - box.left) / box.width) * width;
          const index = rows.length > 1 ? Math.round((px - padL) / step) : 0;
          setHover(Math.max(0, Math.min(rows.length - 1, index)));
        }}
      >
        <defs>
          {SERIES.filter((s) => s.area).map((s) => (
            <linearGradient key={s.key} id={`u-grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity="0.26" />
              <stop offset="100%" stopColor={s.color} stopOpacity="0.02" />
            </linearGradient>
          ))}
        </defs>

        {tokenTicks.map((value) => (
          <g key={`t${value}`}>
            <line x1={padL} x2={width - padR} y1={yToken(value)} y2={yToken(value)} className="u-grid" />
            <text x={padL - 10} y={yToken(value) + 3.5} className="u-axis" textAnchor="end">
              {fmtAxis(value)}
            </text>
          </g>
        ))}

        {costTicks.map((value) => (
          <text
            key={`c${value}`}
            x={width - padR + 10}
            y={yCost(value) + 3.5}
            className="u-axis"
            textAnchor="start"
          >
            ${money(value)}
          </text>
        ))}

        {rows.length ? (
          <>
            <path d={areaFor("cached")} fill="url(#u-grad-cached)" />
            <path d={pathFor("cost")} className="u-line" style={{ stroke: SERIES[0].color }} />
            <path
              d={pathFor("cached")}
              className="u-line u-line-dashed"
              style={{ stroke: SERIES[1].color }}
            />
            <path d={pathFor("input")} className="u-line" style={{ stroke: SERIES[2].color }} />
            <path d={pathFor("output")} className="u-line" style={{ stroke: SERIES[3].color }} />
          </>
        ) : null}

        {hover !== null && rows[hover] ? (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={padT} y2={padT + innerH} className="u-guide" />
            {SERIES.map((s) => (
              <circle
                key={s.key}
                cx={x(hover)}
                cy={s.axis === "money" ? yCost(rows[hover].cost) : yToken(rows[hover][s.key] || 0)}
                r="3.5"
                fill="var(--surface)"
                stroke={s.color}
                strokeWidth="2"
              />
            ))}
          </g>
        ) : null}

        {rows.map((row, i) => {
          const last = rows.length - 1;
          const showTick = i % labelEvery === 0;
          const showLast = i === last && last % labelEvery > labelEvery / 2;
          return showTick || showLast ? (
            <text key={row.t} x={x(i)} y={height - 8} className="u-axis" textAnchor="middle">
              {tickLabel(row.t, days)}
            </text>
          ) : null;
        })}
      </svg>

      {hover !== null && rows[hover] ? (
        <div className="u-tip" style={{ left: `${(x(hover) / width) * 100}%` }} aria-hidden="true">
          <div className="u-tip-time">
            {dayLabel(rows[hover].t)} {days <= 1 ? clock(rows[hover].t) : ""}
          </div>
          <div className="u-tip-row"><i style={{ background: SERIES[0].color }} />成本<b>${money(rows[hover].cost)}</b></div>
          <div className="u-tip-row"><i style={{ background: SERIES[1].color }} />缓存命中<b>{fmtCN(rows[hover].cached)}</b></div>
          <div className="u-tip-row"><i style={{ background: SERIES[2].color }} />输入<b>{fmtCN(rows[hover].input)}</b></div>
          <div className="u-tip-row"><i style={{ background: SERIES[3].color }} />输出<b>{fmtCN(rows[hover].output)}</b></div>
        </div>
      ) : null}

      <div className="u-legend">
        {SERIES.map((s) => (
          <span key={s.key}>
            <i data-dashed={s.dashed ? "true" : undefined} style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function Tile({ label, value, caption, children, hint }) {
  return (
    <div className="u-tile" title={hint}>
      <span className="u-tile-label">
        {label}
        {hint ? <em className="u-info">i</em> : null}
      </span>
      <span className="u-tile-value">{value}</span>
      {caption ? <span className="u-tile-caption">{caption}</span> : null}
      {children}
    </div>
  );
}

export default function Usage() {
  const [range, setRange] = useState("1");
  const [tab, setTab] = useState("logs");
  const [model, setModel] = useState("");
  const [balance, setBalance] = useState(null);
  const [balanceBusy, setBalanceBusy] = useState(false);
  const [autoQuery, setAutoQuery] = useState(() => pref("yhl.balance.auto", false));
  const [interval, setIntervalSec] = useState(() => pref("yhl.balance.interval", 300));
  const [calibrate, setCalibrate] = useState(() => pref("yhl.balance.calibrate", false));
  const query = `/api/usage?days=${range}${model ? `&model=${encodeURIComponent(model)}` : ""}`;
  const { data, loading, error, load } = useData(query);

  const summary = data?.summary || {};
  const buckets = data?.buckets || [];
  const events = data?.events || [];
  const models = data?.models || [];
  const prices = (data?.prices || []).filter((item) => item.model !== "deepseek");

  const loadBalance = useCallback(async (refresh = false) => {
    setBalanceBusy(true);
    try {
      setBalance(await getJSON(`/api/balance${refresh ? "?refresh=1" : ""}`));
    } catch (err) {
      setBalance({ ok: false, error: err instanceof Error ? err.message : "余额查询失败" });
    } finally {
      setBalanceBusy(false);
    }
  }, []);

  useEffect(() => {
    loadBalance(false);
  }, [loadBalance]);

  useEffect(() => {
    if (!autoQuery) return undefined;
    const timer = window.setInterval(() => {
      if (!document.hidden) loadBalance(false);
    }, Math.max(15, interval) * 1000);
    return () => window.clearInterval(timer);
  }, [autoQuery, interval, loadBalance]);

  const factor = balance?.ok && balance.factor ? balance.factor : null;
  const scale = calibrate && factor ? factor : 1;
  const cost = (value) => money((Number(value) || 0) * scale);

  const total = (summary.tokens_in || 0) + (summary.tokens_out || 0);
  const fresh = Math.max(0, (summary.tokens_in || 0) - (summary.tokens_cached || 0));
  const hitRate = summary.cache_rate || 0;
  const rangeLabel = RANGES.find(([key]) => key === range)?.[1] || "今天";

  return (
    <div className="u-page">
      <header className="u-head">
        <div>
          <h1 className="u-title">使用统计</h1>
          <p className="u-sub">查看当前课程的模型调用次数、Token 与成本</p>
        </div>
        <div className="u-filters">
          <label className="u-select">
            <select value={model} onChange={(event) => setModel(event.target.value)} aria-label="按模型筛选">
              <option value="">全部模型</option>
              {models.map((item) => (
                <option key={item.model} value={item.model}>
                  {item.model}
                </option>
              ))}
            </select>
            <Icon name="chevronDown" size={13} />
          </label>
          <label className="u-select">
            <select value={range} onChange={(event) => setRange(event.target.value)} aria-label="时间范围">
              {RANGES.map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
            <Icon name="chevronDown" size={13} />
          </label>
          <IconButton icon="refresh" label="刷新" onClick={load} />
        </div>
      </header>

      {error ? <div className="banner banner-danger">{error}</div> : null}

      <section className="u-hero" aria-label="用量总览">
        <div className="u-hero-main">
          <div className="u-hero-label">
            <span className="u-hero-icon"><Icon name="spark" size={15} /></span>
            真实消耗 Tokens
          </div>
          <div className="u-hero-value">
            {fmtInt(total)}
            <small>≈ {fmtCN(total)}</small>
          </div>
        </div>
        <div className="u-hero-side">
          <div>
            <span className="u-tile-label">总请求数</span>
            <b>{fmtInt(summary.calls)}</b>
          </div>
          <div>
            <span className="u-tile-label">
              总成本
              {scale !== 1 ? <em className="u-cal" title={`估算 × ${factor}（按余额差校准）`}>已校准</em> : null}
            </span>
            <b title="只统计本应用发起的调用；DeepSeek 后台金额还含其他客户端与历史调用">
              {summary.cost_by_currency && Object.keys(summary.cost_by_currency).length > 1
                ? Object.entries(summary.cost_by_currency)
                    .map(([cur, v]) => `${cur === "CNY" ? "¥" : "$"}${cost(v)}`)
                    .join(" + ")
                : `${summary.cost_by_currency?.CNY != null ? "¥" : "$"}${cost(summary.cost)}`}
            </b>
          </div>
        </div>
      </section>

      <section className={`u-balance${balance && !balance.ok ? " u-balance-bad" : ""}`} aria-label="账户余额">
        <div className="u-balance-left">
          <span className="u-tile-label">账户余额</span>
          <div className="u-balance-value">
            {balance == null ? "…" : balance.ok ? (
              <>
                ¥{money(balance.total)}
                <small>{balance.currency}</small>
              </>
            ) : (
              "—"
            )}
          </div>
          <span className="u-balance-note">
            {balance == null
              ? "查询中…"
              : balance.ok
                ? `更新于 ${clock(balance.at)} · ${balance.source}`
                : balance.error}
            {balance?.ok ? (
              <button
                type="button"
                className="u-linkbtn"
                title="充值或换 Key 后，把当前余额设为新的基线"
                onClick={async () => {
                  await postEmpty("/api/balance/reset");
                  loadBalance(true);
                }}
              >
                重置基线
              </button>
            ) : null}
          </span>
        </div>

        <div className="u-balance-mid">
          <div>
            <span className="u-tile-label">余额已消耗</span>
            <b>{balance?.spent != null ? `¥${money(balance.spent)}` : "—"}</b>
            <small>自首次记录</small>
          </div>
          <div>
            <span className="u-tile-label">同期估算</span>
            <b>¥{money(balance?.estimated || 0)}</b>
            <small>按调用记录</small>
          </div>
          <div>
            <span className="u-tile-label">校准系数</span>
            <b>{factor ? `×${factor}` : "—"}</b>
            <small>{factor ? "估算 × 系数" : "需两段余额"}</small>
          </div>
        </div>

        <div className="u-balance-actions">
          <div className="u-balance-row">
            <Switch
              checked={autoQuery}
              onChange={(value) => {
                setAutoQuery(value);
                savePref("yhl.balance.auto", value);
              }}
            >
              自动查询
            </Switch>
            <label className="u-select">
              <select
                value={interval}
                disabled={!autoQuery}
                aria-label="查询间隔"
                onChange={(event) => {
                  const value = Number(event.target.value);
                  setIntervalSec(value);
                  savePref("yhl.balance.interval", value);
                }}
              >
                {INTERVALS.map(([value, label]) => (
                  <option key={value} value={value}>
                    每 {label}
                  </option>
                ))}
              </select>
              <Icon name="chevronDown" size={13} />
            </label>
            <IconButton
              icon="refresh"
              label="立即查询余额"
              disabled={balanceBusy}
              onClick={() => loadBalance(true)}
            />
          </div>
          <Switch
            checked={calibrate}
            onChange={(value) => {
              setCalibrate(value);
              savePref("yhl.balance.calibrate", value);
            }}
          >
            成本按余额校准{factor ? `（×${factor}）` : ""}
          </Switch>
        </div>
      </section>

      <section className="u-tiles">
        <Tile label="新增输入" value={fmtCN(fresh)} hint={`${fmtInt(fresh)} tokens`} />
        <Tile label="Output" value={fmtCN(summary.tokens_out)} hint={`${fmtInt(summary.tokens_out)} tokens`} />
        <Tile label="创建" value="N/A" caption="本模型不单独计费" />
        <Tile label="命中" value={fmtCN(summary.tokens_cached)} hint={`${fmtInt(summary.tokens_cached)} tokens`} />
        <Tile
          label="缓存命中率"
          value={`${(hitRate * 100).toFixed(1)}%`}
          hint={`命中 ${fmtCN(summary.tokens_cached)} / 输入合计 ${fmtCN(summary.tokens_in)}`}
        >
          <div className="u-meter">
            <i style={{ width: `${Math.min(100, hitRate * 100)}%` }} />
          </div>
        </Tile>
        <Tile
          label="缓存节省"
          value={`$${money(summary.cache_saving)}`}
          hint="命中 token 比按未命中计价少花的钱（按各次调用的模型与时段折算）"
        />
        <Tile
          label="每份报告"
          value={summary.cost_per_report == null ? "—" : `$${cost(summary.cost_per_report)}`}
          hint={
            summary.reports
              ? `本范围 ${summary.reports} 份报告，合计 $${cost(summary.report_cost)}（含扫描与评分）`
              : "还没有带报告归属的调用记录"
          }
        />
      </section>

      <section className="u-card">
        <header className="u-card-head">
          <h2>使用趋势</h2>
          <span className="u-card-note">{rangeLabel}</span>
        </header>
        <div className="u-card-body">
          {loading && !data ? (
            <Spinner label="读取用量…" />
          ) : buckets.length ? (
            <Chart buckets={buckets} days={Number(range)} scale={scale} />
          ) : (
            <div className="u-empty">
              <Empty
                icon="usage"
                title="这个范围还没有调用"
                text="生成细则或开始评分后，这里会按时间显示 Token 与成本。"
              />
            </div>
          )}
        </div>
      </section>

      <section className="u-card">
        <div className="u-tabs" role="tablist">
          {[
            ["logs", "请求日志"],
            ["models", "模型统计"],
            ["prices", "计价规则"],
          ].map(([key, label]) => (
            <button key={key} role="tab" aria-selected={tab === key} onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </div>

        {tab === "logs" ? (
          events.length ? (
            <div className="u-table-wrap">
              <table className="u-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>模型</th>
                    <th>输入</th>
                    <th>命中</th>
                    <th>输出</th>
                    <th>成本</th>
                    <th>用时</th>
                    <th>状态</th>
                    <th>来源</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((event, index) => (
                    <tr key={`${event.t}-${index}`}>
                      <td className="u-num">{clock(event.t)}</td>
                      <td className="u-mono">{event.m}</td>
                      <td className="u-num">{fmtInt(event.i)}</td>
                      <td className="u-num">{fmtInt(event.c)}</td>
                      <td className="u-num">{fmtInt(event.o)}</td>
                      <td className="u-num">¥{cost(event.cost)}</td>
                      <td className="u-num">{event.ms ? `${(event.ms / 1000).toFixed(1)}s` : "—"}</td>
                      <td>
                        {event.src === "legacy" ? (
                          <Badge tone="accent">汇总</Badge>
                        ) : event.s === "ok" ? (
                          <Badge tone="ok">成功</Badge>
                        ) : (
                          <Badge tone="danger">失败</Badge>
                        )}
                      </td>
                      <td className="u-dim">{event.src || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="u-empty">
              <Empty icon="usage" title="还没有调用记录" text="跑一次细则生成或评分，这里会逐条出现。" />
            </div>
          )
        ) : null}

        {tab === "models" ? (
          models.length ? (
            <div className="u-table-wrap">
              <table className="u-table">
                <thead>
                  <tr>
                    <th>模型</th>
                    <th>调用</th>
                    <th>输入</th>
                    <th>命中</th>
                    <th>输出</th>
                    <th>成本</th>
                    <th>平均用时</th>
                    <th>失败</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((item) => (
                    <tr key={item.model}>
                      <td className="u-mono">{item.model}</td>
                      <td className="u-num">{item.calls}</td>
                      <td className="u-num">{fmtInt(item.i)}</td>
                      <td className="u-num">{fmtInt(item.c)}</td>
                      <td className="u-num">{fmtInt(item.o)}</td>
                      <td className="u-num">¥{cost(item.cost)}</td>
                      <td className="u-num">{item.avg_ms ? `${(item.avg_ms / 1000).toFixed(1)}s` : "—"}</td>
                      <td className="u-num">{item.errors || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="u-empty"><Empty icon="usage" title="还没有模型调用" /></div>
          )
        ) : null}

        {tab === "prices" ? (
          <div className="u-table-wrap">
            <table className="u-table">
              <thead>
                <tr>
                  <th>模型</th>
                  <th>缓存命中</th>
                  <th>未命中</th>
                  <th>输出</th>
                </tr>
              </thead>
              <tbody>
                {prices.map((item) => (
                  <tr key={item.model}>
                    <td className="u-mono">{item.model}</td>
                    <td className="u-num">¥{item.hit}</td>
                    <td className="u-num">¥{item.miss}</td>
                    <td className="u-num">¥{item.out}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="u-foot">
              单位：元 / 百万 token，表中为高峰价（9:00–12:00、14:00–18:00），其余时段五折。
              价格取自 DeepSeek V4 官方定价，可用 LLM_PRICE_HIT / MISS / OUT 覆盖。
            </p>
          </div>
        ) : null}
      </section>

      <p className="u-note">
        只统计经本应用发起的调用（注入检测、内容安全、隐私脱敏、维度归类、评分），单价按调用发生时段表计算；
        官方后台还会计入其他工具或手工测试的请求，两边数字不会完全一致。
      </p>
    </div>
  );
}
