import json
import os
import re

from ..factory import llm as make_llm

STRUCT_RUBRIC_PROMPT = """你是评估设计专家。依据评分标准文档生成结构化评分细则（JSON）。

## 评分标准文档（唯一事实来源）
{doc}

## 硬性要求
1. 每个评分维度对应文档的一个章节，权重沿用文档的分值占比（合计 100）
2. doc_ref 必填：指向该维度在文档中的具体位置（章节名/条款号）；指向不了的维度不要输出
3. 禁止「整体质量」「是否合理」「是否完整」等无判据条目；每级描述必须是可核对的具体判据（描述性语言，禁止评价词）
   等级 A/B/C/D/E，E = 该维度内容未实现/缺失或严重不合格（未做、整卷跑题、抄袭、白卷），不是"比 D 更差"
4. mechanical 仅当该维度能靠正则/数值比较客观判定时才为 true，并给出 rules；否则 false、rules 为 null
5. rules 仅支持两种：
   {{"type": "exists", "pattern": "正则"}}
   {{"type": "numeric_compare", "pattern": "含捕获组的正则", "op": "<|<=|>|>=|==", "threshold": 数值}}
6. 先识别实验主题（实验名称、被测参量、核心方法与仪器），各级判据必须显式绑定这些主题要素，禁止模板句。
   学科不限：物理、化学、生物、电子、机械、计算机等实验课一律适用
7. 每个维度的判据必须含防跑题条款：报告内容与本实验主题无关时，该维度不得高于 D 级

## 输出（不要代码围栏）
{{"criteria": [
  {{"name": "...", "weight": 10, "mechanical": false, "doc_ref": "文档章节名",
    "levels": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}}, "rules": null}}
]}}"""

CELL_PROMPT = """你是评估设计专家。依据评分标准文档，只为维度「{name}」补全下列空缺字段，其余内容不要改写。

## 评分标准文档（唯一事实来源）
{doc}

## 该行已有内容（仅供参考）
{context}

## 待补全字段
{fields}

## 硬性要求
doc_ref 必须指向文档具体位置（章节名/条款号）；等级描述用可核对的具体判据（描述性语言），
禁止「整体质量」「是否合理」「是否完整」等无判据表述；weight 为 0-100 的数字。

## 输出 JSON（不要代码围栏，只含待补全字段）
{{"weight": 10, "doc_ref": "...", "levels": {{"A": "...", "B": "..."}}}}"""

DEVIATION_PROMPT = """你是评估审核员。对比教师手改后的评分细则与原始标准文档，只找「实质性出入」，不评价风格。

## 原始标准文档
{doc}

## 教师手改后的细则
{rubric}

## 输出 JSON（不要围栏）
{{"warnings": [{{"criterion": "...", "message": "出入点与建议"}}]}}
出入不大时 warnings 为空数组。"""

CALIBRATION_PROMPT = """你是评分校准专家。教师与 AI 各自用同一份细则评了同一份实验报告，请对比差异。

## 细则
{rubric}

## 报告正文
{report_text}

## 教师评分
{teacher_grading}

## AI 评分
{ai_grading}

## 任务
1. 逐维度解释分歧原因
2. 给出让等级边界更清晰的具体修订建议
只输出 JSON：
{{
  "agreements": ["一致的维度"],
  "disagreements": [{{"criterion": "...", "teacher_score": "...", "ai_score": "...",
                      "reason": "...", "suggested_rubric_adjustment": "..."}}],
  "suggested_rubric_revisions": "修订后的完整细则，或 null"
}}"""


def _extract_json(text):
    if not isinstance(text, str):
        return {}
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


class RubricGenerator:
    def __init__(self, llm_client=None, output_dir=None, config=None):
        self.llm = llm_client or make_llm(config)
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(__file__), "..", "output", "rubrics")
        os.makedirs(self.output_dir, exist_ok=True)

    def _ask(self, prompt):
        return _extract_json(self.llm.chat([{"role": "user", "content": prompt}], temperature=0.2))

    def generate_structured(self, criteria_doc):
        """生成结构化细则：doc_ref 缺失的维度丢弃，返回 {"criteria", "warnings"}。"""
        from .rubric_io import new_criterion, normalize_weights
        data = self._ask(STRUCT_RUBRIC_PROMPT.format(doc=criteria_doc))
        raw = data.get("criteria") or []
        valid = [c for c in raw if str(c.get("doc_ref", "")).strip() and str(c.get("name", "")).strip()]
        if not valid:
            raise ValueError("模型未生成带标准文档位置（doc_ref）的维度，请重试或更换模型")
        criteria = [new_criterion(c.get("name", ""), c.get("weight", 0), c.get("mechanical", False),
                                  c.get("doc_ref", ""), c.get("levels"), c.get("rules"))
                    for c in valid]
        warnings = []
        dropped = [c.get("name") or "未命名" for c in raw if c not in valid]
        if dropped:
            warnings.append({"criterion": "、".join(dropped),
                             "message": "这些维度无法指向标准文档的具体位置，已丢弃"})
        return {"criteria": normalize_weights(criteria), "warnings": warnings}

    def generate_cells(self, criteria_doc, name, context, fields):
        maybe = {"name": name, "weight": 0, "doc_ref": "", "levels": {}, "rules": None}
        filled = self._ask(CELL_PROMPT.format(
            doc=criteria_doc, name=name,
            context=json.dumps({**maybe, **(context or {})}, ensure_ascii=False),
            fields=", ".join(fields)))
        if not filled:
            raise ValueError("模型未返回可解析的 JSON，请重试")
        return filled

    def validate_deviation(self, criteria_doc, rubric):
        from .rubric_io import criteria_to_markdown
        data = self._ask(DEVIATION_PROMPT.format(doc=criteria_doc,
                                                 rubric=criteria_to_markdown(rubric)))
        return data.get("warnings", [])

    def calibrate(self, rubric, report_text, teacher_grading, ai_grading):
        return _ask(CALIBRATION_PROMPT.format(
            rubric=rubric, report_text=report_text[:8000],
            teacher_grading=json.dumps(teacher_grading, ensure_ascii=False),
            ai_grading=json.dumps(ai_grading, ensure_ascii=False)))
