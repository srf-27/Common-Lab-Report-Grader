"""LLM 实例工厂：所有调用点经此取客户端，测试可整体替换为假模型。"""

from .web.usage import MeteredLLM


def _make(config):
    return MeteredLLM(config)


def llm(config):
    return _make(config)
