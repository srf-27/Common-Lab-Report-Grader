"""统一持久化入口：默认文件后端；配置 storage.postgres.dsn 时结构化数据全量入 PostgreSQL。

设计要点（其余模块只管调 read_json/write_json/...，不感知后端）：
- key = 会话目录下的相对路径（POSIX 风格）；文件后端映射回磁盘路径，PG 后端映射到
  session_kv 表的一行。路径不在 sessions 目录下（config.yaml、Excel 导出等）时直接走文件。
- PG 存 jsonb：JSON 原样入库；纯文本（.txt/.md）以 JSON 字符串形式入库，读取时解包。
- 静默降级：psycopg 未安装、连接失败或执行出错 → 打一条日志并永久回退文件后端，
  保证没装 PG 的环境行为与原来完全一致。
- 首次连上 PG 时做一次性迁移：把 sessions 目录下已有的 .json/.txt/.md 导入
  （ON CONFLICT DO NOTHING，不覆盖库中已有数据）。
- 图片、上传原件、Excel 导出、Chroma 向量库仍是本地文件，不入库。
"""

import json
import os
import threading

_LOCK = threading.RLock()
_backend = "file"       # "file" | "pg"
_pg_conn = None
_pg_broken_reason = ""

GLOBAL_SID = "__global__"  # sessions.json 等全局文件的伪会话


def configure(config):
    """按配置初始化后端。dsn 优先级：环境变量 ERG_PG_DSN > storage.postgres.dsn。"""
    global _backend, _pg_conn, _pg_broken_reason
    with _LOCK:
        if _backend == "pg" or _pg_broken_reason:
            return
        cfg = ((config or {}).get("storage") or {})
        dsn = os.environ.get("ERG_PG_DSN") or ((cfg.get("postgres") or {}).get("dsn") or "")
        if str(cfg.get("backend", "auto")) == "file":
            return
        if not dsn:
            return
        try:
            import psycopg  # 懒导入：未安装即降级
        except ImportError:
            _pg_broken_reason = "psycopg 未安装"
            _log_fallback()
            return
        try:
            conn = psycopg.connect(dsn, autocommit=True)
            _init_schema(conn)
            _backend = "pg"
            _pg_conn = conn
            _migrate_files(conn)
            print(f"[storage] PostgreSQL 后端已启用（已迁移本地既有数据）")
        except Exception as e:  # 连不上：降级，不让应用起不来
            _pg_broken_reason = str(e)[:200]
            _log_fallback()


def _log_fallback():
    if _pg_broken_reason:
        print(f"[storage] PostgreSQL 不可用（{_pg_broken_reason}），已回退本地文件后端")


def _sessions_dir():
    from .web.state import SESSIONS_DIR  # 函数内读取当前值，兼容测试对目录的动态替换
    return SESSIONS_DIR


def _output_folder():
    from .web.state import OUTPUT_FOLDER
    return OUTPUT_FOLDER


def _resolve(path):
    """返回 (sid, key)；不在 sessions 体系内的路径返回 None（直接走文件）。"""
    path = os.path.abspath(path)
    sessions = os.path.abspath(_sessions_dir())
    if path == sessions or path.startswith(sessions + os.sep):
        rel = os.path.relpath(path, sessions).replace("\\", "/")
        sid, _, key = rel.partition("/")
        return sid, key
    if path == os.path.abspath(os.path.join(_output_folder(), "sessions.json")):
        return GLOBAL_SID, "sessions.json"
    return None


def _init_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS session_kv (
                session_id text NOT NULL,
                key        text NOT NULL,
                value      jsonb NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (session_id, key)
            )""")


def _pg_get(sid, key):
    with _LOCK:
        with _pg_conn.cursor() as cur:
            cur.execute("SELECT value FROM session_kv WHERE session_id = %s AND key = %s",
                        (sid, key))
            row = cur.fetchone()
    return row[0] if row else None


def _pg_put(sid, key, value):
    from psycopg.types.json import Json
    with _LOCK:
        with _pg_conn.cursor() as cur:
            cur.execute(
                """INSERT INTO session_kv (session_id, key, value, updated_at)
                   VALUES (%s, %s, %s, now())
                   ON CONFLICT (session_id, key)
                   DO UPDATE SET value = EXCLUDED.value, updated_at = now()""",
                (sid, key, Json(value)))


def _pg_delete(sid, key):
    with _LOCK:
        with _pg_conn.cursor() as cur:
            cur.execute("DELETE FROM session_kv WHERE session_id = %s AND key = %s", (sid, key))


def _pg_exists(sid, key):
    with _LOCK:
        with _pg_conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM session_kv WHERE session_id = %s AND key = %s LIMIT 1", (sid, key))
            return cur.fetchone() is not None


def _migrate_files(conn):
    """一次性把本地会话数据导入 PG（不覆盖已有行）。"""
    from psycopg.types.json import Json
    count = 0
    roots = [(GLOBAL_SID, os.path.abspath(os.path.join(_output_folder(), "sessions.json")))]
    sessions = os.path.abspath(_sessions_dir())
    if os.path.isdir(sessions):
        for sid in os.listdir(sessions):
            for cur_dir, _dirs, files in os.walk(os.path.join(sessions, sid)):
                for name in files:
                    if os.path.splitext(name)[1].lower() in (".json", ".txt", ".md"):
                        roots.append((sid, os.path.join(cur_dir, name)))
    with conn.cursor() as cur:
        for sid, path in roots:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = f.read()
                if os.path.splitext(path)[1].lower() == ".json":
                    value = json.loads(raw)
                else:
                    value = raw
                key = ("sessions.json" if sid == GLOBAL_SID
                       else os.path.relpath(path, os.path.join(sessions, sid)).replace("\\", "/"))
                cur.execute(
                    """INSERT INTO session_kv (session_id, key, value)
                       VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                    (sid, key, Json(value)))
                count += cur.rowcount or 0
            except (OSError, ValueError):
                continue
    if count:
        print(f"[storage] 已从本地文件迁移 {count} 条会话数据到 PostgreSQL")


# ---------------------------------------------------------------- 公共接口
def read_json(path, default=None):
    if _backend == "pg":
        resolved = _resolve(path)
        if resolved:
            try:
                value = _pg_get(*resolved)
                return value if value is not None else default
            except Exception as e:
                _degrade(e)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data, indent=None):
    if _backend == "pg":
        resolved = _resolve(path)
        if resolved:
            try:
                _pg_put(resolved[0], resolved[1], data)
                return
            except Exception as e:
                _degrade(e)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, path)


def read_text(path, default=""):
    if _backend == "pg":
        resolved = _resolve(path)
        if resolved:
            try:
                value = _pg_get(*resolved)
                if value is None:
                    return default
                # 文本以 JSON 字符串入库
                return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            except Exception as e:
                _degrade(e)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return default


def write_text(path, text):
    if _backend == "pg":
        resolved = _resolve(path)
        if resolved:
            try:
                _pg_put(resolved[0], resolved[1], text)
                return
            except Exception as e:
                _degrade(e)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def exists(path):
    if _backend == "pg":
        resolved = _resolve(path)
        if resolved:
            try:
                return _pg_exists(*resolved)
            except Exception as e:
                _degrade(e)
    return os.path.exists(path)


def remove(path):
    if _backend == "pg":
        resolved = _resolve(path)
        if resolved:
            try:
                _pg_delete(*resolved)
                return
            except Exception as e:
                _degrade(e)
    try:
        os.remove(path)
    except OSError:
        pass


def backend_name():
    return _backend


def _degrade(error):
    """PG 中途故障：记录并永久降级文件后端（本次调用继续走文件）。"""
    global _backend, _pg_broken_reason
    with _LOCK:
        if _backend == "pg":
            _backend = "file"
            _pg_broken_reason = str(error)[:200]
            print(f"[storage] PostgreSQL 操作失败（{_pg_broken_reason}），已回退本地文件后端")
