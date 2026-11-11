"""真模型测试基座：统一走 config.yaml 的 deepseek-flash，不再用 FakeLLM 关键字分流。

真模型输出不确定：断言只看结构 / 状态 / 键，不逐字比对文本。
错误分支（非 JSON、强制异常、残缺分数）真模型无法稳定复现，相关测试各自保留极小本地脚本桩。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiment_report_grader.utils.llm_client import LLMClient

# 两个维度，去掉 rules（C2 已删机械判决字段）
CRITERIA = [
    {"name": "误差分析", "weight": 50, "mechanical": False, "doc_ref": "第三章 误差分析",
     "levels": {"A": "给出 A 类与 B 类不确定度并合成，写出置信概率",
                "B": "给出两类不确定度但未合成", "C": "只做定性描述",
                "D": "只提到误差来源", "E": "完全未涉及误差"}},
    {"name": "数据处理", "weight": 50, "mechanical": False, "doc_ref": "第四章 数据处理",
     "levels": {"A": "逐差法计算并给出结果与单位", "B": "有计算过程但缺单位",
                "C": "只列原始数据", "D": "数据抄录且有错", "E": "无数据"}},
]
RUBRIC = {"criteria": [dict(c) for c in CRITERIA]}

REPORT = """# 实验报告
## 数据记录
用逐差法处理数据，n0 到 n7 共 8 组，逐差求平均值并给出单位。
## 误差分析
A 类不确定度按贝塞尔公式计算，B 类按仪器允差，合成得到总不确定度，置信概率 0.95。
## 结论
结果与理论值吻合，相对误差 1.2%。"""


def require_key():
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("真模型测试需要环境变量 DEEPSEEK_API_KEY（deepseek-flash）")


def client():
    """真 LLMClient：.chat 支持 tools/tool_executor，与判级 function calling 对齐。"""
    require_key()
    return LLMClient()


class RecordingLLM:
    """包一层真客户端：记录每次 prompt（.calls）与调用次数（.count）。

    用于「教师意见不进注入检测器」（B2）这类要看 prompt 内容的断言。
    """

    def __init__(self, inner=None):
        self._inner = inner or client()
        self.calls = []
        self.count = 0

    def chat(self, messages, temperature=0.3, retries=2, **kwargs):
        self.calls.append("\n".join(str(m.get("content", "")) for m in messages))
        self.count += 1
        return self._inner.chat(messages, temperature=temperature, retries=retries, **kwargs)
