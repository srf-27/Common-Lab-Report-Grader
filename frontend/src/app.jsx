import { useEffect, useState } from "react";
import { Link, useRoute } from "./lib/router";
import { useApp } from "./lib/store";
import { Button, Field, Icon, IconButton, Sheet, Spinner } from "./ui";
import { CostMeter } from "./ui/cost";
import Workbench from "./pages/Workbench";
import Rubric from "./pages/Rubric";
import Reports from "./pages/Reports";
import ReportDetail from "./pages/ReportDetail";
import Select from "./pages/Select";
import Progress from "./pages/Progress";
import Results from "./pages/Results";
import Roster from "./pages/Roster";
import Calibration from "./pages/Calibration";
import Mcp from "./pages/Mcp";
import Usage from "./pages/Usage";
import Settings from "./pages/Settings";

const GROUPS = [
  {
    title: "评阅流程",
    items: [
      { to: "/app/rubric", label: "评分细则", icon: "rubric", count: (b) => b.rubric.count },
      { to: "/app/reports", label: "实验报告", icon: "reports", count: (b) => b.reports.total },
      { to: "/app/select", label: "选择评分", icon: "select" },
      { to: "/app/results", label: "评分结果", icon: "results", count: (b) => b.unapproved },
      { to: "/app/roster", label: "花名册", icon: "roster" },
    ],
  },
  {
    title: "系统",
    items: [
      { to: "/app/calibration", label: "评分校准", icon: "calibration" },
      { to: "/app/mcp", label: "插件", icon: "mcp", count: (b) => b.mcp.mounted },
      { to: "/app/usage", label: "用量统计", icon: "usage" },
      { to: "/app/settings", label: "配置", icon: "settings" },
    ],
  },
];

const ALL_ITEMS = [
  { to: "/app/workbench", label: "工作台", icon: "workbench" },
  ...GROUPS.flatMap((group) => group.items),
];

/* 紧凑宽度下的标签栏：HIG 最多 5 项，其余收进「更多」 */
const TABS = [
  { to: "/app/workbench", label: "工作台", icon: "workbench" },
  { to: "/app/rubric", label: "细则", icon: "rubric" },
  { to: "/app/reports", label: "报告", icon: "reports" },
  { to: "/app/results", label: "结果", icon: "results" },
];

const TITLES = {
  "/app/workbench": "工作台",
  "/app/rubric": "评分细则",
  "/app/reports": "实验报告",
  "/app/select": "选择评分",
  "/app/progress": "评分进度",
  "/app/results": "评分结果",
  "/app/roster": "花名册",
  "/app/calibration": "评分校准",
  "/app/mcp": "插件",
  "/app/usage": "用量统计",
  "/app/settings": "配置",
};

const ROUTES = {
  "/app/workbench": Workbench,
  "/app/rubric": Rubric,
  "/app/reports": Reports,
  "/app/select": Select,
  "/app/progress": Progress,
  "/app/results": Results,
  "/app/roster": Roster,
  "/app/calibration": Calibration,
  "/app/mcp": Mcp,
  "/app/usage": Usage,
  "/app/settings": Settings,
};

function resolve(path) {
  if (path.startsWith("/app/report/")) {
    return {
      Component: ReportDetail,
      props: { filename: decodeURIComponent(path.slice("/app/report/".length)) },
      title: "报告详情",
      back: { to: "/app/reports", label: "报告" },
    };
  }
  return { Component: ROUTES[path] || Workbench, props: {}, title: TITLES[path] || "工作台" };
}

export default function App() {
  const { boot, fatal, reload, switchSession, createSession } = useApp();
  const path = useRoute();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [more, setMore] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [titleVisible, setTitleVisible] = useState(false);

  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        setScrolled(window.scrollY > 4);
        setTitleVisible(window.scrollY > 96);
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  if (fatal && !boot) {
    return (
      <div className="content" style={{ maxWidth: 520, paddingTop: 80 }}>
        <div className="banner banner-danger">
          <Icon name="alert" size={16} />
          <div>无法读取应用状态：{fatal}</div>
        </div>
        <div style={{ marginTop: 12 }}>
          <Button onClick={reload}>重试</Button>
        </div>
      </div>
    );
  }

  if (!boot) {
    return (
      <div className="content" style={{ maxWidth: 520, paddingTop: 80 }}>
        <Spinner label="正在载入工作台…" />
      </div>
    );
  }

  const route = resolve(path);
  const { Component, props } = route;
  const activeTo = path.startsWith("/app/report/") ? "/app/reports" : path;
  const compactActive = TABS.some((tab) => tab.to === activeTo) ? activeTo : "__more";

  return (
    <>
      <a className="skip-link" href="#main">
        跳到主内容
      </a>
      <div className="app">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true">
              评
            </div>
            <div style={{ minWidth: 0 }}>
              <div className="brand-title">实验报告评阅</div>
              <div className="brand-sub">本地运行 · 人工终审</div>
            </div>
          </div>

          <div className="course-picker">
            <select
              className="select"
              aria-label="切换课程"
              value={boot.session.id || ""}
              onChange={(event) => switchSession(event.target.value)}
            >
              {boot.sessions.map((session) => (
                <option key={session.id} value={session.id}>
                  {session.name}
                </option>
              ))}
            </select>
            <IconButton
              icon="plus"
              label="新建课程"
              onClick={() => {
                setName("");
                setCreating(true);
              }}
            />
          </div>

          <nav aria-label="主导航">
            <div className="nav-group">
              <Link
                to="/app/workbench"
                className="nav-row"
                aria-current={activeTo === "/app/workbench" ? "page" : undefined}
              >
                <Icon name="workbench" />
                <span>工作台</span>
              </Link>
            </div>
            {GROUPS.map((group) => (
              <div className="nav-group" key={group.title}>
                <div className="nav-group-label">{group.title}</div>
                {group.items.map((item) => {
                  const count = item.count ? item.count(boot) : 0;
                  return (
                    <Link
                      key={item.to}
                      to={item.to}
                      className="nav-row"
                      aria-current={activeTo === item.to ? "page" : undefined}
                    >
                      <Icon name={item.icon} />
                      <span>{item.label}</span>
                      {count ? <span className="nav-count">{count}</span> : null}
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>

          <div className="sidebar-foot">
            <div className="t-caption c-secondary">当前阶段</div>
            <div title={boot.stage.label} style={{ color: "var(--label)" }}>
              {boot.stage.label}
            </div>
          </div>
        </aside>

        <div className="main">
          <div className="toolbar" data-scrolled={scrolled ? "true" : "false"}>
            <span style={{ minWidth: 92 }}>
              {route.back ? (
                <Link to={route.back.to} className="toolbar-back">
                  <Icon name="chevronLeft" size={18} />
                  <span>{route.back.label}</span>
                </Link>
              ) : null}
            </span>
            <div className="toolbar-title" data-visible={titleVisible ? "true" : "false"}>
              {route.title}
            </div>
            <div className="toolbar-actions">
              <IconButton
                icon="ellipsis"
                label="更多"
                className="tabbar-only"
                onClick={() => setMore(true)}
              />
            </div>
          </div>

          <main className="content" id="main" key={`${boot.session.id}:${path}`}>
            <Component {...props} />
          </main>
        </div>
      </div>

      <nav className="tabbar" aria-label="底部导航">
        <div className="tabbar-inner">
          {TABS.map((tab) => (
            <Link
              key={tab.to}
              to={tab.to}
              className="tab"
              aria-current={compactActive === tab.to ? "page" : undefined}
            >
              <Icon name={tab.icon} size={23} />
              <span>{tab.label}</span>
            </Link>
          ))}
          <button
            type="button"
            className="tab"
            aria-current={compactActive === "__more" ? "page" : undefined}
            onClick={() => setMore(true)}
          >
            <Icon name="ellipsis" size={23} />
            <span>更多</span>
          </button>
        </div>
      </nav>

      <Sheet
        open={more}
        title="更多"
        onClose={() => setMore(false)}
        footer={
          <Button variant="filled" onClick={() => setMore(false)}>
            完成
          </Button>
        }
      >
        <div className="list" style={{ boxShadow: "none" }}>
          {ALL_ITEMS.filter((item) => !TABS.some((tab) => tab.to === item.to)).map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="nav-list-row"
              onClick={() => setMore(false)}
            >
              <Icon name={item.icon} size={19} />
              <span className="grow">{item.label}</span>
              <Icon name="chevronRight" size={14} className="row-chevron" />
            </Link>
          ))}
        </div>

        <div className="field" style={{ marginTop: 18 }}>
          <span className="field-label">课程</span>
          <select
            className="select"
            value={boot.session.id || ""}
            aria-label="切换课程"
            onChange={(event) => switchSession(event.target.value)}
          >
            {boot.sessions.map((session) => (
              <option key={session.id} value={session.id}>
                {session.name}
              </option>
            ))}
          </select>
        </div>
        <div style={{ marginTop: 10 }}>
          <Button
            block
            icon="plus"
            onClick={() => {
              setMore(false);
              setName("");
              setCreating(true);
            }}
          >
            新建课程
          </Button>
        </div>
      </Sheet>

      <CostMeter />

      <Sheet
        open={creating}
        title="新建课程"
        text="每门课有独立的细则、报告、评分结果与向量库。"
        onClose={() => setCreating(false)}
        footer={
          <>
            <Button onClick={() => setCreating(false)}>取消</Button>
            <Button
              variant="filled"
              loading={busy}
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                const ok = await createSession(name);
                setBusy(false);
                if (ok) setCreating(false);
              }}
            >
              创建
            </Button>
          </>
        }
      >
        <Field label="课程名称">
          {(id) => (
            <input
              id={id}
              className="input"
              value={name}
              placeholder={`课程 ${boot.sessions.length + 1}`}
              onChange={(event) => setName(event.target.value)}
            />
          )}
        </Field>
      </Sheet>
    </>
  );
}
