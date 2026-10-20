"""测试用假模型：按提示词内容分流，覆盖每条调用链的正常与失败分支。

标记位（写进被评分文本即可触发）：
  IGNORE_ALL   → 注入检测命中
  BAD_CONTENT  → 内容安全拦截
  NO_JSON      → 评分环节返回非 JSON（触发 llm_failed）
"""

import json
import re

CRITERIA = [
    {"name": "误差分析", "weight": 50, "mechanical": False, "doc_ref": "第三章 误差分析",
     "levels": {"A": "给出 A 类与 B 类不确定度并合成，写出置信概率",
                "B": "给出两类不确定度但未合成", "C": "只做定性描述",
                "D": "只提到误差来源", "E": "完全未涉及误差"}, "rules": None},
    {"name": "数据处理", "weight": 50, "mechanical": False, "doc_ref": "第四章 数据处理",
     "levels": {"A": "逐差法计算并给出结果与单位", "B": "有计算过程但缺单位",
                "C": "只列原始数据", "D": "数据抄录且有错", "E": "无数据"}, "rules": None},
]


class FakeLLM:
    def __init__(self):
        self.calls = []

    def chat(self, messages, temperature=0.3, retries=2):
        text = "\n".join(str(m.get("content", "")) for m in messages)
        self.calls.append(text)
        if "提示注入检测器" in text:
            hit = "IGNORE_ALL" in text
            return json.dumps({"is_injection": hit, "techniques": ["override"] if hit else [],
                               "evidence": "忽略以上指令" if hit else "", "confidence": "high"})
        if "内容安全审核员" in text:
            blocked = "BAD_CONTENT" in text
            return json.dumps({"verdict": "blocked" if blocked else "safe",
                               "categories": ["教唆犯罪"] if blocked else [],
                               "evidence": "违法内容" if blocked else "", "confidence": "high"})
        if "个人隐私" in text:
            return '{"entities": [{"type": "name", "value": "张三"}]}'
        if "机械判决器作者" in text:
            return ("```python\nimport re\n\ndef verify(text):\n"
                    "    return {'机械项': {'passed': None, 'detail': '测试桩不判'}}\n```")
        if "归入最相关的评分维度" in text:
            return json.dumps({"assignments": self._assignments(text)}, ensure_ascii=False)
        if "提取学生信息" in text:
            return json.dumps({"学号": "20230001", "姓名": "张三", "班级": "1班", "学院": "物理"},
                              ensure_ascii=False)
        if "结构化评分细则" in text:
            return json.dumps({"criteria": CRITERIA}, ensure_ascii=False)
        if "评估审核员" in text:
            return '{"warnings": []}'
        if "评分校准专家" in text:
            return '{"agreements": ["误差分析"], "disagreements": [], "suggested_rubric_revisions": null}'
        if "实验报告评阅专家" in text:
            if "NO_JSON" in text:
                return "抱歉，我无法给出评分。"
            return json.dumps({"scores": self._scores(text), "summary": "整体合格。", "flags": []},
                              ensure_ascii=False)
        return "{}"

    @staticmethod
    def _names(text):
        m = re.search(r"评分维度[^\n]*\n(.+?)\n规则", text, re.S)
        if not m:
            return []
        block = m.group(1)
        numbered = re.findall(r"^\s*\d+\.\s*(.+?)\s*$", block, re.M)
        if numbered:
            return numbered
        return [n.strip() for n in re.split(r"[、，]", block) if n.strip()]

    def _assignments(self, text):
        payload = text.split("待归类内容（JSON）：", 1)[-1]
        payload = payload.split("\n规则：", 1)[0]
        try:
            items = json.loads(payload.strip())
        except ValueError:
            return []
        names = self._names(text)
        out = []
        for item in items:
            body = str(item.get("text") or "")
            name = names[0] if names else "误差分析"
            for candidate in names:
                if candidate and (candidate[:2] in body or "误差" in body and "误差" in candidate):
                    name = candidate
                    break
            out.append({"id": item.get("id"), "criterion": name})
        return out

    @staticmethod
    def _scores(text):
        names = re.findall(r"### (.+?)（权重", text)
        return {name: {"level": "A" if i == 0 else "B",
                       "evidence": f"{name} 的依据片段",
                       "reasoning": "证据与描述一致"}
                for i, name in enumerate(names)}
