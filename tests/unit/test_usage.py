"""用量统计：cc-switch 口径计价、币种、未定价、旧文件迁移、按课程隔离。"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.web import usage


def _ts(hour, minute=0):
    now = time.localtime()
    return time.mktime((now.tm_year, now.tm_mon, now.tm_mday, hour, minute, 0, 0, 0, -1))


def test_cc_switch_style_cost():
    from experiment_report_grader.web import pricing
    amt, cur = pricing.cost_of("deepseek-flash", 100_000, 50_000, 0, 10_000)
    assert cur == "USD"
    assert abs(amt - (100_000 * 0.15 + 50_000 * 0.003 + 10_000 * 0.6) / 1e6) < 1e-9
    # 四槽齐全的模型：缓存写也计价
    amt2, _ = pricing.cost_of("claude-sonnet-4-5", 0, 0, 1_000_000, 0)
    assert abs(amt2 - 3.75) < 1e-9
    # 未定价：None，不乱算
    assert pricing.cost_of("no-such-model", 1, 0, 0, 1) == (None, None)


def test_model_id_cleaning():
    from experiment_report_grader.web import pricing
    assert pricing.clean_id("deepseek/deepseek-flash:latest") == "deepseek-flash"
    assert pricing.clean_id("claude-haiku-4-5-20251001") == "claude-haiku-4-5"
    assert pricing.clean_id("model@v2") == "model-v2"


def test_pricing_overrides_win():
    import json as _json
    from experiment_report_grader.web import pricing
    real_folder = pricing._output_folder
    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        pricing._output_folder = lambda: td
        pricing.reset_cache()
        with open(os.path.join(td, "pricing_overrides.json"), "w", encoding="utf-8") as f:
            _json.dump({"deepseek-flash": {"input": 1.0, "output": 2.0, "currency": "CNY"}}, f)
        price = pricing.lookup("deepseek-flash")
        assert price["input"] == 1.0 and price["currency"] == "CNY"
        pricing._output_folder = real_folder
        pricing.reset_cache()


def test_record_and_payload():
    with tempfile.TemporaryDirectory() as tmp:
        usage.record(tmp, "deepseek-v4-flash", 10_000, 4_000, 2_000, ms=1200, source="openai")
        usage.record(tmp, "deepseek-v4-flash", 5_000, 0, 1_000, ms=800, status="error")
        data = usage.load(tmp)
        assert data["calls"] == 2 and data["errors"] == 1, data
        assert data["tokens_in"] == 15_000 and data["tokens_cached"] == 4_000
        day = usage.payload(tmp, days=1)
        assert day["summary"]["calls"] == 2
        assert day["summary"]["cache_rate"] > 0
        # 今天固定 24 个小时桶（空时段补 0），只有 1 个模型
        assert len(day["buckets"]) == 24, len(day["buckets"])
        assert day["summary"]["calls"] == 2
        assert len(day["models"]) == 1
        assert any(e["s"] == "error" for e in day["events"])
        assert day["summary"]["errors"] == 1


def test_legacy_file_migrates_to_one_event():
    with tempfile.TemporaryDirectory() as tmp:
        legacy = {"cost": 0.279324, "tokens_in": 24210, "tokens_out": 28863,
                  "calls": 17, "model": "deepseek-flash", "seq": 17}
        with open(os.path.join(tmp, "usage.json"), "w", encoding="utf-8") as f:
            json.dump(legacy, f)
        data = usage.load(tmp)
        assert len(data["events"]) == 1
        assert data["events"][0]["i"] == 24210
        # 旧汇总是按总量估算的假记录，只进「全部」，不进「今天」
        assert usage.payload(tmp, days=0)["summary"]["cost"] == 0.279324
        assert usage.payload(tmp, days=1)["summary"]["calls"] == 0


def test_sessions_are_isolated():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        usage.record(a, "deepseek-v4-flash", 1_000, 0, 100)
        assert usage.load(a)["calls"] == 1
        assert usage.load(b)["calls"] == 0


def test_report_cost_attribution():
    with tempfile.TemporaryDirectory() as tmp:
        usage.set_report("a.docx")
        usage.record(tmp, "deepseek-v4-flash", 10_000, 8_000, 500)
        usage.set_report("b.docx")
        usage.record(tmp, "deepseek-v4-flash", 10_000, 8_000, 500)
        usage.set_report(None)
        usage.record(tmp, "deepseek-v4-flash", 1_000, 0, 100)
        summary = usage.payload(tmp, days=1)["summary"]
        assert summary["reports"] == 2, summary
        assert summary["cost_per_report"] == round(summary["report_cost"] / 2, 4)
        # 不带报告归属的调用不进「每份报告」的分母
        assert summary["report_cost"] < summary["cost"]
