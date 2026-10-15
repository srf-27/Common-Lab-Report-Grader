import os


class OCREngine:
    _instance = None

    def __init__(self, config=None):
        self.config = config or {}
        self.backend = self.config.get("backend", "paddleocr")
        self._engine = None

    @classmethod
    def get(cls, config=None):
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    def _init_engine(self):
        if self.backend == "paddleocr":
            self._engine = PaddleOCREngine(self.config.get("paddleocr", {}))
        elif self.backend == "api":
            self._engine = APIOCREngine(self.config.get("api", {}))
        else:
            raise ValueError(f"Unknown OCR backend: {self.backend}")

    def recognize_bytes(self, img_bytes):
        if self._engine is None:
            self._init_engine()
        return self._engine.recognize_bytes(img_bytes)

    def recognize_file(self, filepath):
        with open(filepath, "rb") as f:
            return self.recognize_bytes(f.read())


class PaddleOCREngine:
    def __init__(self, config):
        import paddleocr
        version = getattr(paddleocr, "__version__", "2.7.0")
        self._major = int(version.split(".")[0])
        lang = config.get("language", "ch")

        if self._major >= 3:
            self._ocr = paddleocr.PaddleOCR(use_textline_orientation=True, lang=lang, enable_mkldnn=False)
        else:
            self._ocr = paddleocr.PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

    def recognize_bytes(self, img_bytes):
        import numpy as np
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        arr = np.array(img)
        if self._major >= 3:
            result = self._ocr.predict(arr)
        else:
            result = self._ocr.ocr(arr, cls=True)
        return self._parse_result(result)

    def _parse_result(self, result):
        if not result:
            return ""
        lines = []
        for page in result:
            if not page:
                continue
            if isinstance(page, dict):
                lines.extend(str(t) for t in page.get("rec_texts", []))
                continue
            for line in page:
                text = line[1][0]
                lines.append(text)
        return "\n".join(lines)


class APIOCREngine:
    def __init__(self, config):
        self.api_url = config.get("api_url", "")
        self.api_key = config.get("api_key", "")
        self.model = config.get("api_model", "glm-4v-flash")

    def recognize_bytes(self, img_bytes):
        import base64
        import requests
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        ext = self._detect_format(img_bytes)
        data_url = f"data:image/{ext};base64,{b64}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请识别并提取这张图片中的所有文字内容，保持原始排版格式。只输出识别到的文字，不要添加任何解释。"},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "temperature": 0.1,
        }
        resp = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _detect_format(self, img_bytes):
        if img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            return "png"
        if img_bytes[:2] == b"\xff\xd8":
            return "jpeg"
        if img_bytes[:4] == b"GIF8":
            return "gif"
        return "png"
