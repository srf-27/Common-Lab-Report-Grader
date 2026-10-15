import re

PRIVACY_PATTERNS = {
    "chinese_name": re.compile(r"(?:姓名[：:]?\s*)([\u4e00-\u9fa5]{2,4})"),
    "student_id": re.compile(r"(?:学号|学生号|编号)[：:]?\s*(\d{6,12})"),
    "phone": re.compile(r"(\d{3}[-.]?\d{4}[-.]?\d{4})"),
    "email": re.compile(r"([\w.+-]+@[\w-]+\.[\w.]+)"),
    "id_card": re.compile(r"(\d{17}[\dXx])"),
}

REPLACEMENTS = {
    "chinese_name": "[姓名已脱敏]",
    "student_id": "[学号已脱敏]",
    "phone": "[手机号已脱敏]",
    "email": "[邮箱已脱敏]",
    "id_card": "[身份证号已脱敏]",
}


def anonymize_text(text):
    anonymized = text
    replacements_made = []
    for key, pattern in PRIVACY_PATTERNS.items():
        matches = pattern.findall(anonymized)
        if matches:
            for match in matches:
                anonymized = anonymized.replace(match, REPLACEMENTS[key])
                replacements_made.append({"type": key, "original": match})
    return anonymized, replacements_made
