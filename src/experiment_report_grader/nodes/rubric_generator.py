import json
import os
import re

from ..factory import llm as make_llm

STRUCT_RUBRIC_PROMPT = """你是评估设计专家。依据评分标准文档生成结构化评分细则（JSON）。

## 评分标准文档（唯一事实来源）
{doc}

## 硬性要求
1. 把文档里的**全部**考核项都提取出来，包括预习报告、课堂表现、考勤、操作、自评等；不要自行删除任何维度，标注 non_report 交给用户决定是否停用。
2. 保留文档原有的细分粒度：文档把某项拆成「方法」「结果」「现象」等子项时，子项分别成维度；不要为了减少维度数量而合并，也不要把多个评分项塞进一个维度。每个维度只收自己那一类证据。
3. doc_ref 必填：指向该维度在文档中的具体位置（章节名/条款号）。无法指向具体条款的维度不要输出。
3. 禁止「整体质量」「是否合理」「是否完整」等无判据条目；每级描述必须是可核对的具体判据（描述性语言，禁止评价词）
   等级 A/B/C/D/E，E = 该维度内容未实现/缺失或严重不合格（未做、整卷跑题、抄袭、白卷），不是"比 D 更差"
4. 报告里通常看不到证据的维度（预习、课堂、考勤、纪律、操作过程、自评、团队合作）标 "non_report": true，其余 false。
   这些维度按大纲原样单列即可，不要与报告维度合并，也不要因为"报告里没有"就不输出。
6. rules 仅支持两种：
   {{"type": "exists", "pattern": "正则"}}
   {{"type": "numeric_compare", "pattern": "含捕获组的正则", "op": "<|<=|>|>=|==", "threshold": 数值}}
7. 先识别实验主题（实验名称、被测参量、核心方法与仪器），各级判据必须显式绑定这些主题要素，禁止模板句。
   学科不限：物理、化学、生物、电子、机械、计算机等实验课一律适用
8. 每个维度的判据必须含防跑题条款：报告内容与本实验主题无关时，该维度不得高于 D 级

## 输出（不要代码围栏）
{{"criteria": [
  {{"name": "...", "weight": 10, "non_report": false, "doc_ref": "文档章节名",
    "levels": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}}, "rules": null}}
]}}"""

STRUCT_PAIR_PROMPT = """你是评估设计专家。给你两份材料，请只为「本次实验的实验报告」生成结构化评分细则（JSON）。

## 材料 A：课程大纲（课程目标、考核方式、报告要求、分值构成）
{outline}

## 材料 B：实验流程 / 实验模板（本次实验的目的、原理、步骤、数据与产物）
{experiment}

## 硬性要求
1. 把大纲里的**全部**考核项都提取出来，包括预习、课堂、考勤、纪律、操作、自评、团队合作；不要自己删，标 non_report 交给用户决定是否停用。
2. 保留大纲原有的细分粒度：大纲把考核项拆成多个子项（如数据处理方法、数据处理结果）时，子项分别成维度；不要为了减少维度数量而合并。每个维度只收自己那一类证据。
3. 权重优先沿用大纲中与报告相关的分值；大纲没有给出时，按报告结构分配，合计 100。全部维度权重合计仍为 100。
4. doc_ref 必须同时指向大纲条目与实验环节，例如「大纲九、成绩评定方法；实验步骤 3 标准曲线」。
5. A/B/C/D/E 判据必须绑定本实验的具体对象与数据（仪器、试剂、参数、图表、计算式），禁止「整体质量」「是否合理」这类无判据表述；E 仅用于该维度未实现/缺失、整卷跑题、抄袭或白卷。
6. 报告里通常看不到证据的维度（预习、课堂、考勤、纪律、操作过程、自评、团队合作）标 "non_report": true，其余 false；
   这些维度按大纲原样单列，不要与报告维度合并，也不要因为"报告里没有"就不输出。
7. ignored 只用于放重复、无法指向大纲条款或明显无效的条目；正常的考核项不要放进去。
9. 只输出 JSON，不要代码围栏：
{{"criteria": [{{"name": "...", "weight": 20, "non_report": false,
  "doc_ref": "大纲章节；实验步骤",
  "levels": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}}, "rules": null}}],
 "ignored": [{{"name": "...", "reason": "..."}}]}}"""

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
        return _extract_json(self.llm.chat([{"role": "user", "content": prompt}],
                                           temperature=0.2, max_tokens=16384))

    def _structure(self, data):
        """把模型输出收敛成 criteria + warnings；没有 doc_ref 的维度丢弃。"""
        from .rubric_io import new_criterion, normalize_weights
        raw = data.get("criteria") or []
        # 报告无关的维度允许缺 doc_ref：先收进来，交给用户在界面上决定是否停用
        valid = [c for c in raw if str(c.get("name", "")).strip()
                 and (str(c.get("doc_ref", "")).strip() or c.get("non_report"))]
        if not valid:
            raise ValueError("模型未生成带标准文档位置（doc_ref）的维度，请重试或更换模型")
        criteria = [new_criterion(c.get("name", ""), c.get("weight", 0), c.get("mechanical", False),
                                  c.get("doc_ref", ""), c.get("levels"), c.get("rules"),
                                  non_report=c.get("non_report", False))
                    for c in valid]
        warnings = []
        dropped = [c.get("name") or "未命名" for c in raw if c not in valid]
        if dropped:
            warnings.append({"criterion": "、".join(dropped),
                             "message": "这些维度无法指向标准文档的具体位置，已丢弃"})
        # 非报告维度默认停用：保住报告维度的判级集中度；用户可随时取消勾选
        if any(not item["non_report"] for item in criteria):
            for item in criteria:
                if item["non_report"]:
                    item["excluded"] = True
        return {"criteria": normalize_weights(criteria), "warnings": warnings}

    def generate_structured(self, criteria_doc):
        """单份标准文档：生成结构化细则。"""
        return self._structure(self._ask(STRUCT_RUBRIC_PROMPT.format(doc=criteria_doc)))

    def generate_structured_pair(self, outline_doc, experiment_doc):
        """大纲 + 实验流程：大纲给目标与权重，实验材料给判据落点。"""
        data = self._ask(STRUCT_PAIR_PROMPT.format(
            outline=outline_doc[:8000], experiment=experiment_doc[:8000]))
        result = self._structure(data)
        for item in data.get("ignored") or []:
            name = str((item or {}).get("name") or "").strip()
            if name:
                result["warnings"].append({
                    "criterion": name,
                    "message": f"未纳入评分：{(item or {}).get('reason') or '报告中缺少对应证据'}"})
        return result

    @staticmethod
    def _cell_value(filled, field):
        if field in ("weight", "doc_ref"):
            return filled.get(field)
        levels = filled.get("levels") if isinstance(filled.get("levels"), dict) else {}
        return levels.get(field, filled.get(field))

    def _missing_cell_fields(self, filled, fields):
        missing = []
        for field in fields:
            value = self._cell_value(filled, field)
            if field == "weight":
                try:
                    if float(value) <= 0:
                        missing.append(field)
                        continue
                except (TypeError, ValueError):
                    missing.append(field)
                    continue
                continue
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field)
        return missing

    @staticmethod
    def _merge_cell(filled, extra):
        for key in ("weight", "doc_ref"):
            value = extra.get(key)
            if value is not None and str(value).strip():
                filled[key] = value
        extra_levels = extra.get("levels") if isinstance(extra.get("levels"), dict) else {}
        for level in "ABCDE":
            value = extra_levels.get(level, extra.get(level))
            if value is not None and str(value).strip():
                filled.setdefault("levels", {})[level] = value
        return filled

    def generate_cells(self, criteria_doc, name, context, fields):
        maybe = {"name": name, "weight": 0, "doc_ref": "", "levels": {}, "rules": None}
        prompt = CELL_PROMPT.format(
            doc=criteria_doc, name=name,
            context=json.dumps({**maybe, **(context or {})}, ensure_ascii=False),
            fields=", ".join(fields))
        filled = self._ask(prompt)
        if not filled:
            raise ValueError("模型未返回可解析的 JSON，请重试")
        missing = self._missing_cell_fields(filled, fields)
        if missing:
            # 保存过空值的字段必须补上，不能因为上下文里是空字符串就跳过
            retry = self._ask(prompt + "\n\n## 上次输出缺少的字段\n"
                              + "、".join(missing) + "\n这些字段必须给出非空内容，不得省略。")
            filled = self._merge_cell(filled, retry or {})
            missing = self._missing_cell_fields(filled, fields)
        if missing:
            raise ValueError(f"模型未补全字段：{'、'.join(missing)}，请重试")
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
