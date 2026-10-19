"""余额查询：解析 DeepSeek 响应、快照差值、校准系数、换账号重置。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.web import balance

CONFIG = {"llm": {"backend": "openai",
                  "openai": {"base_url": "https://api.deepseek.com",
                             "api_key": "sk-test-abcdef", "model": "deepseek-flash"}}}
OTHER = {"llm": {"backend": "openai",
                 "openai": {"base_url": "https://api.deepseek.com",
                            "api_key": "sk-test-zzzzzz", "model": "deepseek-flash"}}}


class Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class Patched:
    """run_all 不提供 pytest 的 monkeypatch：自己记原值、退出时还原。"""

    def __init__(self):
        self.saved = []

    def set(self, obj, name, value):
        self.saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for obj, name, value in reversed(self.saved):
            setattr(obj, name, value)
        return False


def _sandbox(handler):
    with tempfile.TemporaryDirectory() as tmp, Patched() as patch:
        patch.set(balance, "OUTPUT_DIR", tmp)
        patch.set(balance, "PATH", str(Path(tmp) / "balance.json"))
        balance._CACHE.update({"at": 0.0, "key": "", "value": None})
        patch.set(balance.requests, "get", handler)
        yield patch


def _balance(value, currency="CNY"):
    return Resp(200, {"is_available": True,
                      "balance_infos": [{"currency": currency, "total_balance": value}]})


def test_query_parses_deepseek_balance():
    calls = []

    def handler(url, headers=None, timeout=None):
        calls.append(url)
        return _balance("35.94")

    for _ in _sandbox(handler):
        result = balance.query(CONFIG, force=True)
        assert result["ok"] is True, result
        assert result["total"] == 35.94 and result["currency"] == "CNY"
        assert calls[0].endswith("/user/balance")


def test_auth_error_is_reported():
    for _ in _sandbox(lambda *a, **k: Resp(401, {"error": "bad key"})):
        result = balance.query(CONFIG, force=True)
        assert result["ok"] is False
        assert "Key" in result["error"], result


def test_snapshot_spend_and_factor():
    seq = iter(["50.00", "49.00"])
    for _ in _sandbox(lambda *a, **k: _balance(next(seq))):
        events = [{"t": balance.time.time(), "cost": 0.5} for _ in range(2)]
        first = balance.refresh(CONFIG, events, force=True)
        assert first["total"] == 50.0 and first["spent"] == 0.0, first
        second = balance.refresh(CONFIG, events, force=True)
        assert second["spent"] == 1.0, second
        assert second["estimated"] == 1.0
        assert second["factor"] == 1.0


def test_account_change_resets_snapshot():
    seq = iter(["50.00", "10.00"])
    for _ in _sandbox(lambda *a, **k: _balance(next(seq))):
        balance.refresh(CONFIG, [], force=True)
        result = balance.refresh(OTHER, [], force=True)
        assert result["spent"] == 0.0, result
        assert result["first"]["total"] == 10.0
        assert result["estimated"] == 0


def test_ollama_backend_is_rejected():
    with Patched() as patch:
        balance._CACHE.update({"at": 0.0, "key": "", "value": None})
        result = balance.query({"llm": {"backend": "ollama"}}, force=True)
        assert result["ok"] is False
        assert "OpenAI" in result["error"]
