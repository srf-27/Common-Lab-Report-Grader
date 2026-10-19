"""最小 MCP 服务（stdio / 行分隔 JSON-RPC），供测试与本地联调。

用法：
  python tests/fixtures/fake_mcp_server.py
能力：tools/list、tools/call(search_reference)、resources/list、resources/read、prompts/list、prompts/get
"""

import json
import sys

RESOURCES = {
    "ref://physics/uncertainty": "不确定度：A 类按贝塞尔公式 s(x)/√n 计算；B 类按仪器最大允差/√3。"
                                 "逐差法只用于等间隔线性数据，且需 n 为偶数。",
    "ref://physics/youngs-modulus": "杨氏模量 E = 8FLD/(πd²bΔn)，Δn 用逐差法由 n_{i+4}-n_i 求得。",
    "ref://chemistry/titration": "滴定终点以半滴控制，平行测定三次，相对偏差应小于 0.2%。",
}


def reply(msg_id, result=None, error=None):
    payload = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        payload["error"] = {"code": -32000, "message": error}
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(method, params):
    if method == "initialize":
        return {"protocolVersion": "2024-11-05", "capabilities": {"resources": {}, "tools": {}, "prompts": {}},
                "serverInfo": {"name": "fake-physics-refs", "version": "0.1"}}
    if method == "tools/list":
        return {"tools": [{"name": "search_reference",
                           "description": "按关键词检索学科参考",
                           "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}}]}
    if method == "tools/call":
        if params.get("name") != "search_reference":
            return {"content": [{"type": "text", "text": "未知工具"}]}
        query = str((params.get("arguments") or {}).get("query") or "")
        hits = [text for uri, text in RESOURCES.items() if any(w and w in text for w in query.split())]
        return {"content": [{"type": "text", "text": "\n".join(hits) or "无匹配参考"}]}
    if method == "resources/list":
        return {"resources": [{"uri": uri, "name": uri.rsplit("/", 1)[-1], "mimeType": "text/plain"}
                              for uri in RESOURCES]}
    if method == "resources/read":
        uri = params.get("uri")
        if uri not in RESOURCES:
            raise KeyError(f"资源不存在：{uri}")
        return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": RESOURCES[uri]}]}
    if method == "prompts/list":
        return {"prompts": [{"name": "lab_guidance", "description": "实验报告评分口径"}]}
    if method == "prompts/get":
        return {"messages": [{"role": "user", "content": {"type": "text",
                                                          "text": "评阅时以测量不确定度为硬性要求。"}}]}
    raise KeyError(f"未知方法 {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if "id" not in msg:
            continue
        try:
            reply(msg["id"], handle(msg.get("method"), msg.get("params") or {}))
        except KeyError as e:
            reply(msg["id"], error=str(e).strip("'\""))


if __name__ == "__main__":
    main()
