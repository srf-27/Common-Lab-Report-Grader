"""模型客户端：坏掉的代理环境变量不能让首次使用者看到底层异常。"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiment_report_grader.utils import llm_client
from real_llm import client


def test_no_proxy_brackets_are_sanitized():
    saved = {k: os.environ.get(k) for k in ("NO_PROXY", "no_proxy")}
    try:
        # Windows 的 os.environ 大小写不敏感，两个名字其实是同一个变量
        os.environ["NO_PROXY"] = "localhost, [::1],127.0.0.1"
        llm_client._sanitize_no_proxy()
        assert os.environ["NO_PROXY"] == "localhost,::1,127.0.0.1", os.environ["NO_PROXY"]
        # 干净的值原样保留
        os.environ["NO_PROXY"] = "10.0.0.5"
        llm_client._sanitize_no_proxy()
        assert os.environ["NO_PROXY"] == "10.0.0.5"
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_chat_failure_message_is_actionable():
    class Broken(llm_client.LLMClient):
        def __init__(self):
            self.config = {"backend": "openai"}
            self.backend = "openai"

        def _chat_openai(self, *args, **kwargs):
            raise ConnectionError("boom")

    try:
        Broken().chat([{"role": "user", "content": "hi"}], retries=2)
        raise AssertionError("失败应抛错")
    except RuntimeError as e:
        assert "2 次调用失败" in str(e) and "boom" in str(e) and "代理" in str(e), e


def test_real_client_chats():
    """真模型冒烟：deepseek-flash 能正常返回文本。"""
    out = client().chat([{"role": "user", "content": "只回复两个字：正常"}],
                        temperature=0, retries=1)
    assert isinstance(out, str) and out.strip(), out
