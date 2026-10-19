import { useCallback, useEffect, useRef, useState } from "react";
import { errorText, getJSON } from "./api";

export function useData(url) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(Boolean(url));

  const load = useCallback(async () => {
    if (!url) return null;
    try {
      const next = await getJSON(url);
      setData(next);
      setError("");
      return next;
    } catch (err) {
      setError(errorText(err));
      return null;
    } finally {
      setLoading(false);
    }
  }, [url]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  return { data, error, loading, load, setData };
}

/* fn 需要是 useCallback 包装的稳定引用，否则轮询会被反复重建 */
export function usePoll(fn, delay, active) {
  const saved = useRef(fn);
  saved.current = fn;
  useEffect(() => {
    if (!active) return undefined;
    let stopped = false;
    let timer;
    const tick = async () => {
      await saved.current();
      if (!stopped) timer = setTimeout(tick, delay);
    };
    tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [delay, active]);
}

export function useMountedRef() {
  const ref = useRef(true);
  useEffect(() => () => {
    ref.current = false;
  }, []);
  return ref;
}
