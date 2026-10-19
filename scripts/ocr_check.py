#!/usr/bin/env python3
"""OCR 准确性自检：合成图片 → 识别 → 与期望文本比对。

用法：
  python scripts/ocr_check.py                 # 用 config/config.yaml 的 ocr 配置
  python scripts/ocr_check.py --backend api   # 临时改用 api 后端
退出码 0 = 平均相似度 ≥ 0.85，1 = 不达标或后端不可用。
"""

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from experiment_report_grader.utils.llm_client import load_config  # noqa: E402
from experiment_report_grader.utils import ocr_check  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["paddleocr", "api"], help="覆盖配置中的 OCR 后端")
    args = parser.parse_args()
    config = (load_config() or {}).get("ocr", {})
    if args.backend:
        config["backend"] = args.backend
    result = ocr_check.run(config)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not ocr_check.passed(result):
        print("OCR 自检未达标（阈值 0.85）：检查后端安装、密钥或图片质量。")
        return 1
    print("OCR 自检通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
