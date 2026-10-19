import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { errorText, getJSON, postForm } from "./api";
import { toast } from "./toast";

const Ctx = createContext(null);

export function useApp() {
  return useContext(Ctx);
}

export function AppProvider({ children }) {
  const [boot, setBoot] = useState(null);
  const [fatal, setFatal] = useState("");

  const reload = useCallback(async () => {
    try {
      setBoot(await getJSON("/api/bootstrap"));
      setFatal("");
      return true;
    } catch (err) {
      setFatal(errorText(err));
      return false;
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const switchSession = useCallback(
    async (id) => {
      if (!id) return;
      try {
        await postForm("/session/switch", { session_id: id });
        await reload();
        toast("已切换课程", "ok");
      } catch (err) {
        toast(errorText(err), "danger");
      }
    },
    [reload]
  );

  const createSession = useCallback(
    async (name) => {
      try {
        await postForm("/session/new", { name });
        await reload();
        toast("已创建课程", "ok");
        return true;
      } catch (err) {
        toast(errorText(err), "danger");
        return false;
      }
    },
    [reload]
  );

  const removeSession = useCallback(
    async (id) => {
      try {
        await postForm("/session/remove", { session_id: id });
        await reload();
        toast("课程已删除", "ok");
        return true;
      } catch (err) {
        toast(errorText(err), "danger");
        return false;
      }
    },
    [reload]
  );

  const value = useMemo(
    () => ({ boot, fatal, reload, switchSession, createSession, removeSession }),
    [boot, fatal, reload, switchSession, createSession, removeSession]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
