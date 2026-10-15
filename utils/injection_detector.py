import re

INJECTION_PATTERNS = [
    re.compile(r"忽略(以上|前面|之前)", re.IGNORECASE),
    re.compile(r"disregard\s+(previous|above|all)", re.IGNORECASE),
    re.compile(r"ignore\s+(previous|above|all)\s+(instructions|prompts)", re.IGNORECASE),
    re.compile(r"你现在是(?!.*学生)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?!.*student)", re.IGNORECASE),
    re.compile(r"new\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:", re.IGNORECASE),
    re.compile(r"\[INST\]"),
    re.compile(r"<\|im_start\|>"),
    re.compile(r"<\|im_end\|>"),
    re.compile(r"(不要|无需|不用)(评分|打分|判分)", re.IGNORECASE),
    re.compile(r"(直接|必须)(给|打)(满分|高分|通过)", re.IGNORECASE),
    re.compile(r"give\s+(full|maximum)\s+marks?", re.IGNORECASE),
    re.compile(r"(必须|一定|务必)(通过|给.*高分|给.*满分)", re.IGNORECASE),
    re.compile(r"override\s+(previous|system|all)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if|a)\s+", re.IGNORECASE),
    re.compile(r"pretend\s+(you|that)", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all|your)\s+", re.IGNORECASE),
]


def detect_injection(text):
    matches = []
    for pattern in INJECTION_PATTERNS:
        found = pattern.search(text)
        if found:
            matches.append({
                "pattern": pattern.pattern,
                "matched_text": found.group(),
                "position": found.start(),
            })
    is_injection = len(matches) > 0
    return {
        "is_injection": is_injection,
        "match_count": len(matches),
        "matches": matches,
    }
