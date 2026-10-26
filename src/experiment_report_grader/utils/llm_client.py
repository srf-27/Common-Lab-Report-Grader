
import json
import os
import threading
import time

import yaml
from pathlib import Path
from openai import OpenAI

_CLIENTS = {}
_CLIENTS_LOCK = threading.Lock()


def openai_client(api_key, base_url, timeout=300):
    """复用 OpenAI/httpx 连接池；每次 new 客户端会重新做 DNS/TLS 握手。"""
    key = (api_key or "", base_url or "", timeout)
    with _CLIENTS_LOCK:
        client = _CLIENTS.get(key)
        if client is None:
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)
            _CLIENTS[key] = client
        return client


def load_config(config_path=None):
    if config_path is None:
        # Try config/ directory first (enterprise structure), then fallback to parent
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "config" / "config.yaml"
        if not config_path.exists():
            config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class LLMClient:
    def __init__(self, config=None):
        if config is None:
            config = load_config()
        self.config = config["llm"]
        self.backend = self.config["backend"]

    def chat(self, messages, temperature=0.3, retries=2, tools=None, tool_executor=None,
             max_tokens=None):
        last_err = None
        for attempt in range(retries):
            try:
                if self.backend == "openai":
                    return self._chat_openai(messages, temperature, tools=tools,
                                             tool_executor=tool_executor, max_tokens=max_tokens)
                elif self.backend == "ollama":
                    return self._call_ollama(messages)
                elif self.backend == "custom":
                    return self._call_custom(messages, temperature)
            except Exception as e:
                last_err = e
        raise RuntimeError(f"LLM chat failed after {retries} attempts: {last_err}")

    def _chat_openai(self, messages, temperature, tools=None, tool_executor=None,
                     max_tokens=None, on_response=None):
        cfg = self.config["openai"]
        api_key = os.environ.get(cfg["api_key"], cfg["api_key"])
        client = openai_client(api_key, cfg.get("base_url"))

        def create(msgs, with_tools):
            kwargs = dict(model=cfg["model"], temperature=temperature,
                          max_tokens=max_tokens or cfg.get("max_tokens"))
            if with_tools:
                kwargs["tools"] = tools
            started = time.perf_counter()
            try:
                resp = client.chat.completions.create(messages=msgs, **kwargs)
            except Exception:
                if on_response:
                    on_response(None, started, "error")
                raise
            if on_response:
                on_response(resp, started)
            return resp

        if not (tools and tool_executor):
            resp = create(messages, False)
            return resp.choices[0].message.content

        msgs = [dict(m) for m in messages]
        try:
            for _ in range(6):
                resp = create(msgs, True)
                msg = resp.choices[0].message
                calls = getattr(msg, "tool_calls", None)
                if not calls:
                    return msg.content
                msgs.append({"role": "assistant", "content": msg.content or "",
                             "tool_calls": [c.model_dump() for c in calls]})
                for call in calls:
                    try:
                        args = json.loads(call.function.arguments or "{}")
                        output = tool_executor(call.function.name, args)
                    except Exception as e:
                        output = {"error": str(e)[:200]}
                    msgs.append({"role": "tool", "tool_call_id": call.id,
                                 "content": json.dumps(output, ensure_ascii=False)})
            resp = create(msgs, False)
            return resp.choices[0].message.content
        except Exception:
            # 网关不认 tools 时退回普通调用，功能不中断
            resp = create(messages, False)
            return resp.choices[0].message.content

    def chat_stream(self, messages, temperature=0.3, max_tokens=None,
                         tools=None, tool_executor=None):
        """流式对话：逐段 yield ("thinking"|"answer", 增量文本)，末尾 yield ("usage", usage对象)。

        仅 openai 后端真流式（思考型模型的 reasoning_content 走 thinking 事件）；
        ollama/custom 或网关不支持流式时退化为一次性 answer 事件，调用方无感。
        """
        if self.backend != "openai":
            yield "answer", self.chat(messages, temperature=temperature)
            yield "usage", {}
            return
        if tools and tool_executor:
            # 工具循环走非流式（流式与 function calling 并用会复杂化计费）
            text = self._chat_openai(messages, temperature, tools=tools,
                                     tool_executor=tool_executor, max_tokens=max_tokens)
            yield "answer", text
            yield "usage", {}
            return
        cfg = self.config["openai"]
        api_key = os.environ.get(cfg["api_key"], cfg["api_key"])
        client = openai_client(api_key, cfg.get("base_url"))
        try:
            stream = client.chat.completions.create(
                model=cfg["model"], messages=messages, temperature=temperature,
                max_tokens=max_tokens or cfg.get("max_tokens"), stream=True,
                stream_options={"include_usage": True})
        except Exception:
            # 个别网关不认 stream_options 或不支持流式：退回非流式
            yield "answer", self._chat_openai(messages, temperature, max_tokens=max_tokens)
            yield "usage", {}
            return
        usage = {}
        for chunk in stream:
            u = getattr(chunk, "usage", None)
            if u is not None:
                usage = u
                continue
            for choice in chunk.choices or []:
                delta = choice.delta or {}
                reasoning = getattr(delta, "reasoning_content", None)
                if not reasoning:
                    reasoning = (getattr(delta, "model_extra", None) or {}).get("reasoning_content")
                if reasoning:
                    yield "thinking", reasoning
                if delta.content:
                    yield "answer", delta.content
        yield "usage", usage

    def _call_ollama(self, messages):
        import requests
        cfg = self.config["ollama"]
        url = f"{cfg['base_url']}/api/chat"
        payload = {"model": cfg["model"], "messages": messages, "stream": False}
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    def _call_custom(self, messages, temperature):
        cfg = self.config["custom"]
        client = openai_client(cfg["api_key"], cfg["base_url"])
        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content
