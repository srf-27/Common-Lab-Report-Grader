"""真实浏览器点击测试（Chrome DevTools Protocol，不依赖 Playwright）。

单独运行：python tests/e2e/click_test.py

起 Flask → 起 headless Chrome → 逐页导航、点击、断言、截图。
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websocket

ROOT = Path(__file__).resolve().parents[2]
PROJ = str(ROOT)
PORT = 5077
DBG = 9333
BASE = f"http://127.0.0.1:{PORT}"
OUT = str(Path(__file__).resolve().parent / "_artifacts")
CHROME = os.environ.get("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")

PAGES = [
    ("/app/workbench", "工作台"),
    ("/app/rubric", "评分细则"),
    ("/app/reports", "实验报告"),
    ("/app/select", "选择评分"),
    ("/app/results", "评分结果"),
    ("/app/roster", "花名册"),
    ("/app/calibration", "评分校准"),
    ("/app/mcp", "插件"),
    ("/app/usage", "用量统计"),
    ("/app/settings", "配置"),
]


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.6)
        return s.connect_ex(("127.0.0.1", port)) == 0


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.seq = 0
        self.session = None

    def send(self, method, params=None, session=None):
        self.seq += 1
        msg = {"id": self.seq, "method": method, "params": params or {}}
        if session or self.session:
            msg["sessionId"] = session or self.session
        self.ws.send(json.dumps(msg))
        while True:
            data = json.loads(self.ws.recv())
            if data.get("id") == self.seq:
                if "error" in data:
                    raise RuntimeError(f"{method}: {data['error']}")
                return data.get("result", {})

    def eval(self, expr):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")

    def goto(self, url):
        self.send("Page.navigate", {"url": url})
        for _ in range(120):
            time.sleep(0.15)
            state = self.eval("document.readyState")
            if state == "complete":
                time.sleep(0.45)
                return
        raise RuntimeError(f"页面加载超时: {url}")

    def shot(self, name):
        data = self.send("Page.captureScreenshot", {"format": "png"})
        import base64
        with open(os.path.join(OUT, name + ".png"), "wb") as f:
            f.write(base64.b64decode(data["data"]))


def wait_server():
    for _ in range(80):
        if port_open(PORT):
            try:
                urllib.request.urlopen(BASE + "/api/bootstrap", timeout=2).read()
                return True
            except Exception:
                pass
        time.sleep(0.4)
    return False


def main():
    os.makedirs(OUT, exist_ok=True)
    server = subprocess.Popen(
        [os.path.join(PROJ, ".venv/Scripts/python.exe"), "run.py", "--port", str(PORT)],
        cwd=PROJ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not wait_server():
        server.terminate()
        print("FAIL 服务器未就绪")
        sys.exit(1)

    profile = os.path.join(OUT, "_profile")
    chrome = subprocess.Popen([
        CHROME, "--headless=new", f"--remote-debugging-port={DBG}",
        f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*",
        "--disable-gpu", "--window-size=1440,900", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    rows = []

    def add(kind, name, ok, detail=""):
        rows.append({"kind": kind, "name": name, "ok": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'} [{kind}] {name}" + (f" — {detail}" if detail else ""), flush=True)

    try:
        ws_url = None
        for _ in range(60):
            try:
                info = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{DBG}/json/version", timeout=2).read())
                ws_url = info["webSocketDebuggerUrl"]
                break
            except Exception:
                time.sleep(0.4)
        if not ws_url:
            raise RuntimeError("Chrome 调试端口未就绪")

        cdp = CDP(ws_url)
        target = cdp.send("Target.createTarget", {"url": "about:blank"})
        attached = cdp.send("Target.attachToTarget", {"targetId": target["targetId"], "flatten": True})
        cdp.session = attached["sessionId"]
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        cdp.send("Emulation.setDeviceMetricsOverride",
                 {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})

        errors = cdp.eval("() => []")
        cdp.eval("window.__errs = []; window.addEventListener('error', e => window.__errs.push(String(e.message)));"
                 "window.__cerr = [];  const oe = console.error; console.error = (...a) => { window.__cerr.push(a.join(' ')); oe(...a); };")

        cdp.goto(BASE + "/app/workbench")
        add("启动", "工作台可打开", bool(cdp.eval("document.body.innerText.length > 50")))

        for path, title in PAGES:
            cdp.goto(BASE + path)
            body = cdp.eval("document.body.innerText") or ""
            add("页面", f"{title}", title in body, f"{len(body)} 字符")
            cdp.shot(path.strip("/").replace("/", "_"))

        add("页面", "无运行时错误", not (cdp.eval("window.__errs") or []),
            "; ".join((cdp.eval("window.__errs") or [])[:3]))

        cdp.goto(BASE + "/app/workbench")
        for path, title in PAGES[:4]:
            cdp.eval(f"document.querySelector('a[href=\"{path}\"]').click()")
            time.sleep(0.7)
            add("点击", f"侧栏 → {title}", cdp.eval("location.pathname") == path,
                cdp.eval("location.pathname"))

        cdp.goto(BASE + "/app/reports")
        total = cdp.eval("document.querySelectorAll('.list-row[data-interactive]').length") or 0
        for label in ("未评分", "已评分", "全部"):
            clicked = cdp.eval(
                "(() => { const b = [...document.querySelectorAll('button.chip')]"
                f".find(x => x.textContent.trim().startsWith('{label}')); if (!b) return false; b.click(); return true; }})()")
            if not clicked:
                add("筛选", f"报告页「{label}」", False, "找不到按钮")
                continue
            time.sleep(0.6)
            got = cdp.eval("document.querySelectorAll('.list-row[data-interactive]').length") or 0
            add("筛选", f"报告页「{label}」", got <= total, f"{got} 行 / 全部 {total}")

        cdp.goto(BASE + "/app/select")
        base_rows = cdp.eval("document.querySelectorAll('.list-row[data-interactive]').length") or 0
        for label in ("未评分", "需重评", "已评分", "被标记", "全部"):
            clicked = cdp.eval(
                "(() => { const b = [...document.querySelectorAll('button.chip')]"
                f".find(x => x.textContent.trim().startsWith('{label}')); if (!b) return false; b.click(); return true; }})()")
            if not clicked:
                add("筛选", f"选卷页「{label}」", False, "找不到按钮")
                continue
            time.sleep(0.6)
            got = cdp.eval("document.querySelectorAll('.list-row[data-interactive]').length") or 0
            add("筛选", f"选卷页「{label}」", got <= base_rows, f"{got} 行 / 全部 {base_rows}")
        cdp.shot("select_filtered")

        cdp.goto(BASE + "/app/usage")
        time.sleep(1.2)
        body = cdp.eval("document.body.innerText") or ""
        add("统计", "指标与图表区渲染", ("Tokens" in body or "token" in body) and "使用趋势" in body)
        cdp.shot("usage")

        cdp.goto(BASE + "/app/reports")
        has_link = cdp.eval("!!document.querySelector('a[href^=\"/app/report/\"]')")
        if has_link:
            cdp.eval("document.querySelector('a[href^=\"/app/report/\"]').click()")
            time.sleep(0.9)
            add("点击", "进入报告详情", "/app/report/" in (cdp.eval("location.pathname") or ""),
                cdp.eval("location.pathname"))
            cdp.shot("report_detail")

        cdp.send("Emulation.setDeviceMetricsOverride",
                 {"width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True})
        cdp.goto(BASE + "/app/workbench")
        time.sleep(0.8)
        add("响应式", "390px 出现底部标签栏",
            bool(cdp.eval("!!document.querySelector('[class*=tabbar]')")))
        cdp.shot("mobile_workbench")

        cdp.send("Emulation.setDeviceMetricsOverride",
                 {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        cdp.goto(BASE + "/app/reports")
        cdp.eval("document.body.focus()")
        cdp.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Tab", "code": "Tab",
                                            "windowsVirtualKeyCode": 9})
        cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Tab", "code": "Tab",
                                            "windowsVirtualKeyCode": 9})
        time.sleep(0.3)
        tag = cdp.eval("document.activeElement && document.activeElement.tagName")
        add("无障碍", "Tab 能聚焦", tag not in (None, "", "BODY"), str(tag))

        add("控制台", "无 console.error", not (cdp.eval("window.__cerr") or []),
            "; ".join((cdp.eval("window.__cerr") or [])[:3]))

        cdp.ws.close()
    finally:
        chrome.terminate()
        server.terminate()
        for proc in (chrome, server):
            try:
                proc.wait(timeout=8)
            except Exception:
                proc.kill()

    bad = [r for r in rows if not r["ok"]]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} 通过")
    with open(os.path.join(OUT, "click_report.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
