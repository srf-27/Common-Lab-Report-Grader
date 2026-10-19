import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/* 提示条：底部居中堆叠、悬停暂停计时、进出场只做位移 + 淡入（Sonner 原则） */
let seq = 0;
const items = [];
const listeners = new Set();
const timers = new Map();

function emit() {
  listeners.forEach((fn) => fn());
}

export function dismiss(id) {
  const item = items.find((entry) => entry.id === id);
  if (!item || item.closing) return;
  item.closing = true;
  item.open = false;
  emit();
  clearTimeout(timers.get(id));
  setTimeout(() => {
    const index = items.indexOf(item);
    if (index >= 0) items.splice(index, 1);
    emit();
  }, 220);
}

function schedule(item) {
  clearTimeout(timers.get(item.id));
  timers.set(
    item.id,
    setTimeout(() => dismiss(item.id), item.tone === "danger" ? 5200 : 3600)
  );
}

export function toast(message, tone = "default") {
  const item = { id: ++seq, message, tone, open: false };
  items.push(item);
  while (items.length > 3) dismiss(items[0].id);
  emit();
  requestAnimationFrame(() => {
    item.open = true;
    emit();
  });
  schedule(item);
  return item.id;
}

export function Toaster() {
  const [list, setList] = useState([]);
  useEffect(() => {
    const sync = () => setList(items.slice());
    listeners.add(sync);
    sync();
    return () => listeners.delete(sync);
  }, []);

  if (!list.length) return null;
  return createPortal(
    <div className="toaster" role="status" aria-live="polite">
      {list.map((item) => (
        <div
          key={item.id}
          className="toast"
          data-open={item.open ? "true" : "false"}
          data-tone={item.tone}
          onMouseEnter={() => clearTimeout(timers.get(item.id))}
          onMouseLeave={() => item.open && schedule(item)}
          onClick={() => dismiss(item.id)}
        >
          <span className="toast-dot" aria-hidden="true" />
          <span>{item.message}</span>
        </div>
      ))}
    </div>,
    document.body
  );
}
