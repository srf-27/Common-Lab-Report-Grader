"""用量统计：峰谷计价、缓存命中折扣、旧文件迁移、按课程隔离。"""
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


def test_peak_and_offpeak_rates():
    peak = usage.rates_for("deepseek-v4-flash", _ts(10))
    off = usage.rates_for("deepseek-v4-flash", _ts(20))
    assert peak == (0.10, 3.0, 9.0), peak
    assert off == (0.05, 1.5, 4.5), off


def test_cost_splits_cache_hit():
    ts = _ts(10)
    assert abs(usage.cost_of("deepseek-v4-flash", 1_000_000, 0, 0, ts) - 0.10) < 1e-9
    assert abs(usage.cost_of("deepseek-v4-flash", 0, 1_000_000, 0, ts) - 3.0) < 1e-9
    assert abs(usage.cost_of("deepseek-v4-flash", 1_000_000, 1_000_000, 0, ts) - 3.10) < 1e-9


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
