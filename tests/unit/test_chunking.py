"""分块：跨行公式 \\[ ... \\] 不能被空行切开，否则 KaTeX 永远匹配不到成对分隔符。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.app import _chunks

MATH = """原理如下：

\\[

E=\\frac{F/S}{\\Delta L/L},

\\]

其中 F 为拉力。"""


def test_math_block_stays_whole():
    chunks = _chunks(MATH)
    assert len(chunks) == 3, chunks
    math = chunks[1]
    assert math.count("\\[") == 1 and math.count("\\]") == 1
    assert "E=\\frac" in math
    assert chunks[2].startswith("其中")


def test_plain_paragraphs_split():
    chunks = _chunks("第一段。\n\n第二段。\n\n第三段。")
    assert chunks == ["第一段。", "第二段。", "第三段。"]


def test_unclosed_math_merges_rest():
    chunks = _chunks("开头\n\n\\[\nx=1\n\n尾巴")
    assert len(chunks) == 2 and "尾巴" in chunks[1]


def test_limit_respected():
    assert len(_chunks("\n\n".join(f"段{i}" for i in range(50)), limit=8)) == 8


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_chunking ok")
