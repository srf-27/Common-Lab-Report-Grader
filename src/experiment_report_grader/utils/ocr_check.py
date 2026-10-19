"""OCR 自检：合成一张含中文、数字与公式符号的图片，跑一遍识别并给出相似度。

由「模型配置」页的「运行 OCR 自检」按钮与 scripts/ocr_check.py 共用。
"""

import difflib
import io

CASES = ("实验报告 2023 逐差法", "E=2.20e11 Pa", "不确定度 σ=0.35 mm")


def _font(size=34):
    from PIL import ImageFont
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
                 "/System/Library/Fonts/PingFang.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render(text):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (900, 140), "white")
    ImageDraw.Draw(image).text((60, 46), text, fill="black", font=_font())
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def run(config=None):
    """返回 {"ok", "cases":[{expected, actual, similarity}], "average"}；失败带 error。"""
    try:
        from .ocr_engine import OCREngine
        engine = OCREngine.get(config or {})
    except Exception as e:
        return {"ok": False, "error": f"OCR 后端初始化失败：{e}"[:300], "cases": []}
    cases = []
    for expected in CASES:
        try:
            actual = engine.recognize_bytes(_render(expected))
        except Exception as e:
            return {"ok": False, "error": f"识别失败：{e}"[:300], "cases": cases}
        actual = (actual or "").strip()
        cases.append({"expected": expected, "actual": actual,
                      "similarity": round(difflib.SequenceMatcher(
                          None, expected.replace(" ", ""), actual.replace(" ", "")).ratio(), 3)})
    return {"ok": True, "cases": cases,
            "average": round(sum(c["similarity"] for c in cases) / len(cases), 3)}


def passed(result, threshold=0.85):
    return bool(result.get("ok")) and result.get("average", 0) >= threshold
