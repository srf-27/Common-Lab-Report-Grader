"""MCP 服务器注册表：读写 config/mcp.yaml（不含课程挂载，挂载在会话目录）。"""

import os
import re

import yaml

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "config", "mcp.yaml")

def load_servers():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}
    servers = data.get("servers") or {}
    return servers if isinstance(servers, dict) else {}


def save_servers(servers):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump({"servers": servers}, f, allow_unicode=True, sort_keys=True)


def upsert(name, cfg):
    servers = load_servers()
    servers[name] = cfg
    save_servers(servers)
    return servers


def remove(name):
    servers = load_servers()
    servers.pop(name, None)
    save_servers(servers)
    return servers


def parse_form(form):
    """把表单转成服务器配置；名字非法或缺连接参数时抛 ValueError。"""
    name = (form.get("name") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+", name or ""):
        raise ValueError("插件名称只能用字母、数字、- _ .")
    transport = (form.get("transport") or "stdio").strip().lower()
    if transport not in ("stdio", "http"):
        raise ValueError("transport 只能是 stdio 或 http")
    note = (form.get("note") or "").strip()[:120]
    if transport == "http":
        url = (form.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("HTTP 插件需要 http(s):// 开头的 url")
        return {"transport": "http", "url": url, "headers": {}, "note": note}
    command = (form.get("command") or "").strip()
    if not command:
        raise ValueError("stdio 插件需要 command")
    args = [a for a in (form.get("args") or "").replace("\n", " ").split(" ") if a]
    env = {}
    for line in (form.get("env") or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            if k.strip():
                env[k.strip()] = v.strip()
    return {"transport": "stdio", "command": command, "args": args, "env": env, "note": note}
