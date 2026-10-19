"""MCP 客户端（JSON-RPC 2.0）：stdio 子进程与 HTTP 两种传输，够用即可。

只实现评分需要的六个方法：initialize / tools / resources / prompts。
任何异常都收敛为 MCPError，由调用方兜底（评分绝不因插件不可用而中断）。
"""

import json
import queue
import subprocess
import threading
import time

import requests

PROTOCOL = "2024-11-05"
CALL_TIMEOUT = 25.0


class MCPError(RuntimeError):
    pass


class _Stdio:
    """子进程传输：按行收发 JSON-RPC。"""

    def __init__(self, command, args=(), env=None, cwd=None):
        cmd = [command, *[str(a) for a in (args or [])]]
        full_env = None
        if env:
            import os
            full_env = {**os.environ, **{str(k): str(v) for k, v in env.items()}}
        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            cwd=cwd, env=full_env, text=True, encoding="utf-8", errors="replace", bufsize=1)
        self._inbox = queue.Queue()
        self._alive = True
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._inbox.put(json.loads(line))
            except ValueError:
                continue
        self._alive = False

    def send(self, payload):
        if not self._alive or self._proc.poll() is not None:
            raise MCPError("MCP 子进程已退出")
        self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def recv(self, msg_id, deadline):
        while time.time() < deadline:
            try:
                msg = self._inbox.get(timeout=max(0.05, deadline - time.time()))
            except queue.Empty:
                break
            if msg.get("id") == msg_id:
                return msg
        raise MCPError("MCP 子进程响应超时")

    def close(self):
        try:
            self._proc.stdin.close()
            self._proc.terminate()
            self._proc.wait(timeout=3)
        except Exception:
            pass


class _Http:
    def __init__(self, url, headers=None, **_):
        if not url:
            raise MCPError("缺少 url")
        self.url = url
        self.headers = {"Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        **(headers or {})}
        self.session_id = ""

    def send(self, payload):
        headers = dict(self.headers)
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        resp = requests.post(self.url, headers=headers, json=payload, timeout=CALL_TIMEOUT)
        if resp.status_code >= 400:
            raise MCPError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        self.session_id = resp.headers.get("Mcp-Session-Id") or self.session_id
        return self._parse(resp, payload.get("id"))

    def _parse(self, resp, msg_id):
        ctype = resp.headers.get("Content-Type", "")
        if "text/event-stream" not in ctype:
            return resp.json()
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                try:
                    msg = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if msg.get("id") == msg_id:
                    return msg
        raise MCPError("SSE 响应中没有匹配的 JSON-RPC 消息")

    def close(self):
        pass


class MCPClient:
    def __init__(self, cfg):
        cfg = cfg or {}
        if (cfg.get("transport") or "stdio").lower() == "http":
            self.transport = _Http(cfg.get("url"), cfg.get("headers"))
        else:
            command = cfg.get("command")
            if not command:
                raise MCPError("缺少 command")
            self.transport = _Stdio(command, cfg.get("args"), cfg.get("env"), cfg.get("cwd"))
        self.cfg = cfg
        self.server_info = {}
        self._next_id = 0
        self._started = False

    def _request(self, method, params=None):
        self._next_id += 1
        msg_id = self._next_id
        payload = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}
        deadline = time.time() + CALL_TIMEOUT
        if isinstance(self.transport, _Http):
            msg = self.transport.send(payload)
        else:
            self.transport.send(payload)
            msg = self.transport.recv(msg_id, deadline)
        if "error" in msg:
            raise MCPError(f"{method} 失败：{msg['error'].get('message') or msg['error']}")
        return msg.get("result") or {}

    def _notify(self, method, params=None):
        try:
            self.transport.send({"jsonrpc": "2.0", "method": method, "params": params or {}})
        except Exception:
            pass

    def start(self):
        if self._started:
            return self
        result = self._request("initialize", {
            "protocolVersion": PROTOCOL, "capabilities": {},
            "clientInfo": {"name": "experiment-report-grader", "version": "1.0"}})
        self.server_info = result.get("serverInfo") or {}
        self._notify("notifications/initialized")
        self._started = True
        return self

    def list_tools(self):
        return (self.start()._request("tools/list").get("tools") or [])

    def call_tool(self, name, arguments=None):
        return self.start()._request("tools/call", {"name": name, "arguments": arguments or {}})

    def list_resources(self):
        return (self.start()._request("resources/list").get("resources") or [])

    def read_resource(self, uri):
        return (self.start()._request("resources/read", {"uri": uri}).get("contents") or [])

    def list_prompts(self):
        return (self.start()._request("prompts/list").get("prompts") or [])

    def get_prompt(self, name, arguments=None):
        return (self.start()._request("prompts/get", {"name": name, "arguments": arguments or {}}))

    def close(self):
        self.transport.close()


def describe(cfg):
    """连接并列出能力；失败抛 MCPError，由路由转成可读错误。"""
    client = MCPClient(cfg)
    try:
        client.start()
        out = {"server": client.server_info, "tools": [], "resources": [], "prompts": [],
               "errors": []}
        for key, fn in (("tools", client.list_tools), ("resources", client.list_resources),
                        ("prompts", client.list_prompts)):
            try:
                out[key] = fn()
            except MCPError as e:
                out["errors"].append(f"{key}: {e}")
        return out
    finally:
        client.close()


def _text_of(result):
    parts = []
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "\n".join(p for p in parts if p).strip()


def _prompt_text(result):
    return "\n".join(str(m.get("content") or "") for m in (result.get("messages") or [])
                     if isinstance(m, dict)).strip()


def collect(servers, mount, query, budget=None):
    """按课程挂载拉取学科参考：resources / search_tool / prompt。

    servers: {名称: 服务器配置}；mount: 课程挂载（servers/resources/search_tool/prompt/max_chars）。
    返回 (拼好的参考文本, 每台服务器的状态列表)。任何失败都只写进状态，不影响评分。
    """
    budget = budget or int(mount.get("max_chars") or 4000)
    patterns = mount.get("resources") or []
    parts, status = [], []
    for name in mount.get("servers") or []:
        cfg = (servers or {}).get(name)
        entry = {"name": name, "ok": False, "error": "", "count": 0}
        if not cfg:
            entry["error"] = "服务器未在配置中登记"
            status.append(entry)
            continue
        client = None
        try:
            client = MCPClient(cfg).start()
            entry["server"] = client.server_info.get("name") or name
            chunks = []
            for res in client.list_resources():
                uri = str(res.get("uri") or "")
                if patterns and not _match(uri, patterns):
                    continue
                for content in client.read_resource(uri):
                    text = str(content.get("text") or "").strip()
                    if text:
                        chunks.append(f"【{res.get('name') or uri}】\n{text}")
                if sum(len(c) for c in chunks) >= budget:
                    break
            tool = mount.get("search_tool")
            if tool:
                chunks.append(f"【检索 {tool}】\n" + _text_of(client.call_tool(tool, {"query": query})))
            prompt = mount.get("prompt")
            if prompt:
                chunks.append("【学科指引】\n" + _prompt_text(client.get_prompt(prompt, {"topic": query})))
            text = "\n\n".join(c for c in chunks if c.strip())[:budget]
            if text:
                parts.append(f"### 插件：{name}\n{text}")
                entry["count"] = len(chunks)
            entry["ok"] = True
        except Exception as e:
            entry["error"] = str(e)[:200]
        finally:
            if client is not None:
                client.close()
        status.append(entry)
        if sum(len(p) for p in parts) >= budget:
            break
    return "\n\n".join(parts)[:budget], status


def _match(uri, patterns):
    from fnmatch import fnmatch
    return any(fnmatch(uri, p) for p in patterns)
