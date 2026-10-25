"""提示词前缀缓存：固定内容必须排在每份报告不同的内容之前。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.nodes.grader import GRADING_SYSTEM, GRADING_USER


def test_system_message_holds_rules_and_schema():
    assert "判定规则" in GRADING_SYSTEM
    assert '"scores"' in GRADING_SYSTEM
    # 规则与输出格式都必须留在系统消息里，不能落到每份报告都变的尾部
    assert "{report_text}" not in GRADING_SYSTEM


def test_user_message_orders_stable_before_variable():
    order = [
        "{criteria_block}",
        "{references}",
        "{dimension_notes}",
        "{exemplar_shots}",
        "{report_text}",
        "{image_descriptions}",
    ]
    positions = [GRADING_USER.index(token) for token in order]
    assert positions == sorted(positions), positions


def test_template_formats_without_missing_fields():
    rendered = GRADING_USER.format(
        criteria_block="### 维度（权重 50%）\n- A: x",
        references="（无插件参考）",
        dimension_notes="（暂无）",
        exemplar_shots="（暂无已终审范例）",
        report_text="报告正文",
        image_descriptions="（本报告无图片）",
        extra_notes="（无）",
    )
    assert rendered.index("### 维度") < rendered.index("报告正文")
