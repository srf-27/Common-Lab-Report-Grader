import re

BLOCKED_PATTERNS = [
    re.compile(r"(制造|制作|合成).{0,10}(炸药|炸弹|毒品|毒药)", re.IGNORECASE),
    re.compile(r"(如何|怎么|怎样).{0,10}(杀人|自杀|自残)", re.IGNORECASE),
    re.compile(r"(购买|获取).{0,10}(枪支|弹药|管制刀具|毒品)", re.IGNORECASE),
    re.compile(r"(hack|crack|破解).{0,10}(password|密码|系统|服务器)", re.IGNORECASE),
    re.compile(r"(攻击|入侵|渗透).{0,10}(系统|网络|服务器|数据库)", re.IGNORECASE),
]

WARN_PATTERNS = [
    re.compile(r"(暴力|血腥|残忍)", re.IGNORECASE),
    re.compile(r"(歧视|侮辱|诽谤).{0,10}(女性|男性|种族|民族|宗教)", re.IGNORECASE),
    re.compile(r"(赌博|诈骗|传销)", re.IGNORECASE),
]


def check_content_safety(text):
    blocked = []
    for pattern in BLOCKED_PATTERNS:
        found = pattern.search(text)
        if found:
            blocked.append({"pattern": pattern.pattern, "matched_text": found.group()})

    warned = []
    for pattern in WARN_PATTERNS:
        found = pattern.search(text)
        if found:
            warned.append({"pattern": pattern.pattern, "matched_text": found.group()})

    if blocked:
        return {"verdict": "blocked", "blocked": blocked, "warned": warned}
    if warned:
        return {"verdict": "warning", "blocked": blocked, "warned": warned}
    return {"verdict": "safe", "blocked": [], "warned": []}
