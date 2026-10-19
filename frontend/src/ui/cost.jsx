import { useEffect, useRef, useState } from "react";
import { getJSON } from "../lib/api";
import { useApp } from "../lib/store";
import { Icon } from "./index";

const money = (value) => {
  const n = Number(value) || 0;
  return n < 1 ? n.toFixed(3) : n.toFixed(2);
};

const tokens = (value) => {
  const n = Number(value) || 0;
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`;
  if (n >= 1e4) return `${(n / 1e4).toFixed(1)}万`;
  return String(n);
};

/* 左下角的花费牌：按课程累计 token 与费用，每次消耗弹一条上飘提示 */
export function CostMeter() {
  const { boot } = useApp();
  const sessionId = boot.session.id;
  const [usage, setUsage] = useState(boot.usage || {});
  const [bursts, setBursts] = useState([]);
  const seen = useRef({ cost: boot.usage?.cost || 0, seq: boot.usage?.seq || 0 });
  const seq = useRef(0);

  useEffect(() => {
    seen.current = { cost: boot.usage?.cost || 0, seq: boot.usage?.seq || 0 };
    setUsage(boot.usage || {});
    setBursts([]);
  }, [sessionId]);

  useEffect(() => {
    let stopped = false;
    let timer;
    const tick = async () => {
      if (!document.hidden) {
        try {
          const next = await getJSON("/api/usage?days=0");
          if (stopped) return;
          const data = next.summary || {};
          const delta = (data.cost || 0) - seen.current.cost;
          if (delta > 0.00004 && (data.seq || 0) > seen.current.seq) {
            const id = ++seq.current;
            setBursts((list) => [...list, { id, text: `+${delta < 0.01 ? delta.toFixed(3) : delta.toFixed(2)}` }]);
            setTimeout(() => setBursts((list) => list.filter((item) => item.id !== id)), 1900);
          }
          seen.current = { cost: data.cost || 0, seq: data.seq || 0 };
          setUsage(data);
        } catch {
          /* 服务重启时静默重试 */
        }
      }
      if (!stopped) timer = setTimeout(tick, 2200);
    };
    timer = setTimeout(tick, 1200);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [sessionId]);

  const total = (usage.tokens_in || 0) + (usage.tokens_out || 0);
  const title = `本课程已调用模型 ${usage.calls || 0} 次，输入 ${usage.tokens_in || 0} / 输出 ${usage.tokens_out || 0} token`;

  return (
    <div className="cost-meter" title={title}>
      <div className="cost-bursts" aria-hidden="true">
        {bursts.map((item) => (
          <span className="cost-burst" key={item.id}>
            {item.text}
          </span>
        ))}
      </div>
      {total ? (
        <>
          <span className="cost-icon" aria-hidden="true">
            <Icon name="spark" size={13} />
          </span>
          <span className="cost-amount">¥{money(usage.cost)}</span>
          <span className="cost-tokens">{tokens(total)}</span>
        </>
      ) : (
        <>
          <span className="cost-icon" aria-hidden="true">
            <Icon name="spark" size={13} />
          </span>
          <span className="cost-idle">尚未产生消耗</span>
        </>
      )}
      <span className="sr-only" aria-live="polite">
        {bursts.length ? `本次消耗 ${bursts[bursts.length - 1].text} 元` : ""}
      </span>
    </div>
  );
}
