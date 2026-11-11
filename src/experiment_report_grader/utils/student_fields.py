"""学生字段归一：花名册/导出列名 → 标准键，取值的纯函数（web 与 nodes 共用，避免反向依赖）。"""

STUDENT_FIELDS = ["班级", "学院", "学号", "姓名"]


def canonical_field(header):
    """把「学生学号」「学生姓名」这类导出列名归一到标准键（学号/姓名/班级/学院）。"""
    text = str(header or "")
    return next((field for field in STUDENT_FIELDS if field in text), text)


def student_value(student, header):
    """按标准键取学生字段，取不到再退回花名册原始列名（兼容早先按列名写入的数据）。"""
    student = student or {}
    for key in (canonical_field(header), header):
        value = str(student.get(key, "") or "").strip()
        if value:
            return value
    return ""
