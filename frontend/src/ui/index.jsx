import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { LEVELS, LEVEL_LABEL } from "../lib/format";
import { Link } from "../lib/router";

/* 图标按 SF Symbols 的语义与笔画规范绘制（1.9 描边、圆角端点） */
const PATHS = {
  workbench: (
    <>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.8" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.8" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.8" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.8" />
    </>
  ),
  rubric: (
    <>
      <path d="M8 6.5h12M8 12h12M8 17.5h8" />
      <circle cx="4" cy="6.5" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="4" cy="12" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="4" cy="17.5" r="1.1" fill="currentColor" stroke="none" />
    </>
  ),
  reports: (
    <>
      <path d="M6.5 3.5h7.2L19 8.8v10.4a1.8 1.8 0 0 1-1.8 1.8H6.5a1.8 1.8 0 0 1-1.8-1.8V5.3a1.8 1.8 0 0 1 1.8-1.8z" />
      <path d="M13.4 3.7v5.1h5.3M8.5 13h7M8.5 16.6h4.5" />
    </>
  ),
  select: (
    <>
      <rect x="3.4" y="3.4" width="17.2" height="17.2" rx="4.2" />
      <path d="M8 12.2l2.7 2.7 5.3-5.6" />
    </>
  ),
  results: <path d="M4 20.2V11.4M9.4 20.2V4.6M14.8 20.2v-6.4M20.2 20.2V8" />,
  roster: (
    <>
      <circle cx="9" cy="8" r="3.3" />
      <path d="M3 19.6v-1.1a3.8 3.8 0 0 1 3.8-3.8h4.4a3.8 3.8 0 0 1 3.8 3.8v1.1" />
      <path d="M16.3 5a3.3 3.3 0 0 1 0 6.1M21 19.6v-1.1a3.8 3.8 0 0 0-2.8-3.7" />
    </>
  ),
  calibration: (
    <>
      <circle cx="12" cy="12" r="8.3" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="12" cy="12" r="0.9" fill="currentColor" stroke="none" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7.6h8.6M17.6 7.6H20M4 16.4h3.4M12.4 16.4H20" />
      <circle cx="15.1" cy="7.6" r="2.2" />
      <circle cx="9.9" cy="16.4" r="2.2" />
    </>
  ),
  mcp: (
    <>
      <path d="M9.2 3.4v5.4M14.8 3.4v5.4" />
      <path d="M6.4 8.8h11.2v2.7a5.6 5.6 0 0 1-11.2 0z" />
      <path d="M12 17.4v3.2" />
    </>
  ),
  plus: <path d="M12 5.2v13.6M5.2 12h13.6" />,
  trash: (
    <>
      <path d="M4.2 6.8h15.6M9.4 6.8V4.5h5.2v2.3" />
      <path d="M6.6 6.8l.8 12.1a1.5 1.5 0 0 0 1.5 1.4h6.2a1.5 1.5 0 0 0 1.5-1.4l.8-12.1" />
    </>
  ),
  x: <path d="M6.4 6.4l11.2 11.2M17.6 6.4L6.4 17.6" />,
  chevronRight: <path d="M9.5 5.2l6.6 6.8-6.6 6.8" />,
  chevronDown: <path d="M5.2 9.5l6.8 6.6 6.8-6.6" />,
  chevronLeft: <path d="M14.5 5.2l-6.6 6.8 6.6 6.8" />,
  upload: (
    <>
      <path d="M12 16.2V4.6M7.4 9.2L12 4.6l4.6 4.6" />
      <path d="M4.4 15.6v2.6a1.6 1.6 0 0 0 1.6 1.6h12a1.6 1.6 0 0 0 1.6-1.6v-2.6" />
    </>
  ),
  download: (
    <>
      <path d="M12 4.6v11.6M7.4 11.6L12 16.2l4.6-4.6" />
      <path d="M4.4 16.4v1.8a1.6 1.6 0 0 0 1.6 1.6h12a1.6 1.6 0 0 0 1.6-1.6v-1.8" />
    </>
  ),
  external: (
    <>
      <path d="M13.8 4.4h5.8v5.8" />
      <path d="M19.4 4.6l-8.2 8.2" />
      <path d="M17.6 13.6v4.6a1.6 1.6 0 0 1-1.6 1.6H5.4a1.6 1.6 0 0 1-1.6-1.6V7.6a1.6 1.6 0 0 1 1.6-1.6h4.4" />
    </>
  ),
  refresh: (
    <>
      <path d="M20.1 11.4a8.1 8.1 0 1 0-.8 4.5" />
      <path d="M20.1 4.8v6.6h-6.6" />
    </>
  ),
  alert: (
    <>
      <path d="M12 4.2l8.4 15.4H3.6z" />
      <path d="M12 10.2v4.2M12 17.4h.01" />
    </>
  ),
  check: <path d="M4.8 12.6l4.7 4.7L19.2 6.9" />,
  play: <path d="M8.2 5.2l10.4 6.8-10.4 6.8z" fill="currentColor" stroke="none" />,
  pause: <path d="M9.2 4.8v14.4M14.8 4.8v14.4" />,
  eye: (
    <>
      <path d="M2.4 12S6 5.8 12 5.8 21.6 12 21.6 12S18 18.2 12 18.2 2.4 12 2.4 12z" />
      <circle cx="12" cy="12" r="2.6" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.4" />
      <path d="M15.8 15.8l4.4 4.4" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8.3" />
      <path d="M12 11.2v5.1M12 8.1h.01" />
    </>
  ),
  pen: (
    <>
      <path d="M15.6 4.6l3.8 3.8-9.6 9.6-4.6.8.8-4.6z" />
      <path d="M13.8 6.4l3.8 3.8" />
    </>
  ),
  lock: (
    <>
      <rect x="4.8" y="10.4" width="14.4" height="9.6" rx="2.4" />
      <path d="M8.4 10.4V7.8a3.6 3.6 0 0 1 7.2 0v2.6" />
    </>
  ),
  ellipsis: (
    <>
      <circle cx="5.6" cy="12" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="18.4" cy="12" r="1.5" fill="currentColor" stroke="none" />
    </>
  ),
  folder: (
    <path d="M3.6 7.4a1.8 1.8 0 0 1 1.8-1.8h4l1.8 2.2h7.4a1.8 1.8 0 0 1 1.8 1.8v8.2a1.8 1.8 0 0 1-1.8 1.8H5.4a1.8 1.8 0 0 1-1.8-1.8z" />
  ),
  usage: (
    <>
      <path d="M4 19.6h16" />
      <path d="M6.6 16.4v-4.6M11 16.4V6.6M15.4 16.4v-6.2M19.8 16.4V9" />
    </>
  ),
  spark: (
    <>
      <path d="M12 3.6l1.7 4.4 4.4 1.7-4.4 1.7L12 15.8l-1.7-4.4L5.9 9.7l4.4-1.7z" />
      <path d="M18.2 15.2l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" />
    </>
  ),
  person: (
    <>
      <circle cx="12" cy="8.2" r="3.6" />
      <path d="M4.8 20.2v-1.4a4.4 4.4 0 0 1 4.4-4.4h5.6a4.4 4.4 0 0 1 4.4 4.4v1.4" />
    </>
  ),
};

export function Icon({ name, size = 17, ...rest }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {PATHS[name] || PATHS.info}
    </svg>
  );
}

const BTN_VARIANTS = {
  gray: "",
  filled: "btn-filled",
  tinted: "btn-tinted",
  plain: "btn-plain",
  destructive: "btn-destructive",
};

const btnClass = (variant, size, block, className) =>
  ["btn", BTN_VARIANTS[variant] ?? "", size ? `btn-${size}` : "", block ? "btn-block" : "", className]
    .filter(Boolean)
    .join(" ");

export function Button({
  children,
  variant = "gray",
  size,
  icon,
  loading,
  block,
  className = "",
  ...rest
}) {
  return (
    <button className={btnClass(variant, size, block, className)} {...rest}>
      {loading ? <span className="spinner" /> : icon ? <Icon name={icon} size={15} /> : null}
      {children}
    </button>
  );
}

export function LinkButton({ to, children, variant = "gray", size, icon, block, className = "" }) {
  return (
    <Link to={to} className={btnClass(variant, size, block, className)}>
      {icon ? <Icon name={icon} size={15} /> : null}
      {children}
    </Link>
  );
}

export function IconButton({ icon, label, className = "", ...rest }) {
  return (
    <button className={`icon-btn ${className}`} aria-label={label} title={label} {...rest}>
      <Icon name={icon} size={18} />
    </button>
  );
}

export function Field({ label, hint, children, className = "" }) {
  const id = useId();
  const child = typeof children === "function" ? children(id) : children;
  return (
    <div className={`field ${className}`}>
      {label ? (
        <label className="field-label" htmlFor={id}>
          {label}
        </label>
      ) : null}
      {child}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </div>
  );
}

/* 分组容器：HIG inset grouped —— 标题在上、说明在下，内容是一张圆角卡 */
export function Group({ title, note, footer, children, actions, className = "" }) {
  return (
    <section className={`group ${className}`}>
      {title || actions ? (
        <div className="group-header">
          <span className="group-title">{title}</span>
          <span className="row" style={{ gap: 6 }}>
            {note ? <span className="group-note">{note}</span> : null}
            {actions}
          </span>
        </div>
      ) : null}
      <div className="list">{children}</div>
      {footer ? <div className="group-footer">{footer}</div> : null}
    </section>
  );
}

/* 列表行：HIG 信息行的标准结构（图标 / 标题+副标题 / 值 / 展开箭头） */
export function ListRow({
  icon,
  title,
  sub,
  value,
  chevron,
  selected,
  trailing,
  to,
  onClick,
  children,
  ...rest
}) {
  const interactive = Boolean(to || onClick);
  const content = (
    <>
      {icon ? (
        <span className="row-icon">
          <Icon name={icon} size={16} />
        </span>
      ) : null}
      {children || (
        <span className="row-main">
          <span className="row-title" style={{ display: "block" }}>
            {title}
          </span>
          {sub ? (
            <span className="row-sub" style={{ display: "block" }}>
              {sub}
            </span>
          ) : null}
        </span>
      )}
      {value !== undefined ? <span className="row-value">{value}</span> : null}
      {trailing}
      {chevron ? <Icon name="chevronRight" size={15} className="row-chevron" /> : null}
    </>
  );

  const common = {
    "data-interactive": interactive ? "true" : undefined,
    "data-inset": icon ? "icon" : undefined,
    "data-selected": selected ? "true" : undefined,
  };

  if (to) {
    return (
      <Link to={to} className="list-row" {...common} {...rest}>
        {content}
      </Link>
    );
  }
  if (onClick) {
    return (
      <button type="button" className="list-row" onClick={onClick} {...common} {...rest}>
        {content}
      </button>
    );
  }
  return (
    <div className="list-row" {...common} {...rest}>
      {content}
    </div>
  );
}

export function Badge({ tone = "", outline, children, className = "" }) {
  return (
    <span
      className={`badge${tone ? ` badge-${tone}` : ""}${outline ? " badge-outline" : ""} ${className}`}
    >
      {children}
    </span>
  );
}

export function LevelBadge({ level, title }) {
  return (
    <span
      className={`level level-${level || "none"}`}
      title={title || LEVEL_LABEL[level] || "未评"}
      aria-label={`等级 ${level || "未评"}`}
    >
      {level || "–"}
    </span>
  );
}

export function LevelPicker({ value, onChange, disabled, allowEmpty, label = "等级" }) {
  return (
    <div className="level-picker" role="group" aria-label={label}>
      {LEVELS.map((level) => (
        <button
          key={level}
          type="button"
          data-level={level}
          aria-pressed={value === level}
          aria-label={`${level} ${LEVEL_LABEL[level]}`}
          disabled={disabled}
          onClick={() => onChange(allowEmpty && value === level ? "" : level)}
        >
          {level}
        </button>
      ))}
    </div>
  );
}

export function Segmented({ options, value, onChange, label }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => {
        const [key, text] = Array.isArray(option) ? option : [option.value, option.label];
        return (
          <button key={key} type="button" aria-pressed={value === key} onClick={() => onChange(key)}>
            {text}
          </button>
        );
      })}
    </div>
  );
}

export function Switch({ checked, onChange, children, disabled, ...rest }) {
  return (
    <label className="switch">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        disabled={disabled}
        {...rest}
      />
      {children ? <span>{children}</span> : null}
    </label>
  );
}

export function Chip({ active, children, count, ...rest }) {
  return (
    <button className="chip" aria-pressed={active} {...rest}>
      {children}
      {count !== undefined ? <em>{count}</em> : null}
    </button>
  );
}

export function Progress({ value = 0, tone }) {
  const width = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div
      className="progress"
      role="progressbar"
      aria-valuenow={width}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className="progress-fill" data-tone={tone} style={{ width: `${width}%` }} />
    </div>
  );
}

export function Stat({ label, value, suffix }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {suffix ? <small>{suffix}</small> : null}
      </div>
    </div>
  );
}

export function Banner({ tone = "", icon = "info", children, actions }) {
  return (
    <div className={`banner${tone ? ` banner-${tone}` : ""}`} role="note">
      <Icon name={icon} size={16} />
      <div className="grow">{children}</div>
      {actions}
    </div>
  );
}

export function Empty({ icon = "info", title, text, action }) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon name={icon} size={20} />
      </div>
      <div className="empty-title">{title}</div>
      {text ? <p className="empty-text">{text}</p> : null}
      {action ? <div style={{ marginTop: 14 }}>{action}</div> : null}
    </div>
  );
}

export function Spinner({ label = "载入中…" }) {
  return (
    <div className="center-loader" role="status">
      <span className="spinner" style={{ width: 18, height: 18 }} />
      <span>{label}</span>
    </div>
  );
}

/* 折叠：整行可点，只展开一层（HIG disclosure） */
export function Disclosure({ summary, meta, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const [ever, setEver] = useState(defaultOpen);
  const toggle = () => {
    setOpen(!open);
    setEver(true);
  };
  return (
    <>
      <div className="list-row" style={{ gap: 10 }}>
        <button className="disc-toggle" aria-expanded={open} onClick={toggle}>
          <Icon name="chevronRight" size={14} className="disc-chevron" />
          <span className="row-main">{summary}</span>
        </button>
        {meta ? (
          <div className="row" style={{ gap: 6 }}>
            {meta}
          </div>
        ) : null}
      </div>
      <div className="disc-body" data-open={open ? "true" : "false"}>
        <div className="disc-inner">
          <div className="disc-pad">{ever ? children : null}</div>
        </div>
      </div>
    </>
  );
}

/* Sheet：移动端从底部升起，常规宽度居中成对话框（HIG 模态规范） */
export function Sheet({ open, title, text, onClose, children, footer, wide }) {
  const [mounted, setMounted] = useState(open);
  const [shown, setShown] = useState(false);
  const panelRef = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (open) {
      setMounted(true);
      const raf = requestAnimationFrame(() => setShown(true));
      return () => cancelAnimationFrame(raf);
    }
    setShown(false);
    const timer = setTimeout(() => setMounted(false), 320);
    return () => clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open || !mounted) return undefined;
    const previous = document.activeElement;
    const selector =
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const onKey = (event) => {
      if (event.key === "Escape") {
        closeRef.current?.();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const nodes = Array.from(panelRef.current.querySelectorAll(selector)).filter(
        (node) => node.offsetParent !== null
      );
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    // 只在打开时聚焦一次；跟着每次渲染重跑会把中文输入法的组合过程打断
    if (!panelRef.current?.contains(document.activeElement)) {
      panelRef.current?.querySelector(selector)?.focus?.({ preventScroll: true });
    }
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus?.({ preventScroll: true });
    };
  }, [open, mounted]);

  if (!mounted) return null;
  return createPortal(
    <div
      className="overlay"
      data-open={shown ? "true" : "false"}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose?.();
      }}
    >
      <div
        className="sheet"
        data-wide={wide ? "true" : undefined}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={panelRef}
      >
        <div className="sheet-grabber" aria-hidden="true" />
        <div className="sheet-header">
          <h2 className="sheet-title">{title}</h2>
          {text ? <p className="sheet-text">{text}</p> : null}
        </div>
        {children ? <div className="sheet-body">{children}</div> : null}
        {footer ? <div className="sheet-footer">{footer}</div> : null}
      </div>
    </div>,
    document.body
  );
}

export function Dropzone({ accept, multiple, onFiles, title, hint, disabled, selected = [] }) {
  const inputRef = useRef(null);
  const [over, setOver] = useState(false);
  const depth = useRef(0);

  const pick = (files) => {
    const list = Array.from(files || []);
    if (list.length) onFiles(multiple ? list : [list[0]]);
  };

  const openPicker = () => {
    if (!disabled) inputRef.current?.click();
  };

  const names = selected.map((item) => item.name || String(item));

  return (
    <div
      className="dropzone"
      data-over={over ? "true" : undefined}
      data-disabled={disabled ? "true" : undefined}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label={title || "上传文件"}
      onClick={openPicker}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openPicker();
        }
      }}
      onDragEnter={(event) => {
        event.preventDefault();
        if (disabled) return;
        depth.current += 1;
        setOver(true);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) event.dataTransfer.dropEffect = "copy";
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        depth.current = Math.max(0, depth.current - 1);
        if (!depth.current) setOver(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        event.stopPropagation();
        depth.current = 0;
        setOver(false);
        if (!disabled) pick(event.dataTransfer.files);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        hidden
        onChange={(event) => {
          pick(event.target.files);
          event.target.value = "";
        }}
      />
      <div className="dropzone-inner">
        <span className="dropzone-icon" aria-hidden="true">
          <Icon name="upload" size={22} />
        </span>
        <span className="dropzone-title">
          {names.length
            ? `已选 ${names.length} 个文件`
            : title || "拖拽文件到这里，或点击选择"}
        </span>
        <span className="dropzone-hint">
          {names.length ? names.join(" · ") : hint}
        </span>
      </div>
    </div>
  );
}

export function AutoTextarea({ value, minHeight = 56, className = "", ...rest }) {
  const ref = useRef(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.max(minHeight, node.scrollHeight + 2)}px`;
  }, [value, minHeight]);
  return (
    <textarea
      ref={ref}
      className={`textarea ${className}`}
      style={{ minHeight }}
      value={value}
      {...rest}
    />
  );
}

export function PageHead({ title, sub, actions, crumbs }) {
  return (
    <>
      {crumbs?.length ? (
        <nav className="crumbs" aria-label="面包屑">
          {crumbs.map((crumb, index) => (
            <span className="row" style={{ gap: 4 }} key={`${crumb.label}-${index}`}>
              {index ? <Icon name="chevronRight" size={10} /> : null}
              {crumb.to ? <Link to={crumb.to}>{crumb.label}</Link> : <span>{crumb.label}</span>}
            </span>
          ))}
        </nav>
      ) : null}
      <header className="page-head">
        <h1 className="t-large-title">{title}</h1>
        {sub ? <p className="page-sub">{sub}</p> : null}
        {actions ? <div className="page-actions">{actions}</div> : null}
      </header>
    </>
  );
}
