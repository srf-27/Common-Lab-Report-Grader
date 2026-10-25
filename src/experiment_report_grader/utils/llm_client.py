
import os
import threading

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

    def chat(self, messages, temperature=0.3, retries=2):
        last_err = None
        for attempt in range(retries):
            try:
                if self.backend == "openai":
                    return self._call_openai(messages, temperature)
                elif self.backend == "ollama":
                    return self._call_ollama(messages)
                elif self.backend == "custom":
                    return self._call_custom(messages, temperature)
            except Exception as e:
                last_err = e
        raise RuntimeError(f"LLM chat failed after {retries} attempts: {last_err}")

    def _call_openai(self, messages, temperature):
        cfg = self.config["openai"]
        api_key = os.environ.get(cfg["api_key"], cfg["api_key"])
        client = openai_client(api_key, cfg.get("base_url"))
        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=messages,
            temperature=temperature,
            max_tokens=cfg.get("max_tokens"),
        )
        return resp.choices[0].message.content

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
