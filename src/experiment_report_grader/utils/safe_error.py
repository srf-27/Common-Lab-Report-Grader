"""异常文本打码：把绝对路径的目录部分换成 <路径已隐藏>，只留末段文件名。

直出前端的错误常带服务器目录结构（盘符路径、pymupdf 的 filename='...' repr），
这一层统一收敛，日志/内部记录不走这里，仍可保留完整路径便于排障。
"""

import re

_MASK = "<路径已隐藏>"
# Windows 盘符路径（盘符前不能是字母，避开 http://）或 POSIX 绝对路径（/ 前不能是 \w : /）
_PATH_RE = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/][^\s'\"<>|]*|(?<![\w:/])/[^\s'\"<>|]*")


def _mask_path(match):
    full = match.group(0)
    sep = "\\" if "\\" in full else "/"
    tail = re.split(r"[\\/]", full)[-1]
    return f"{_MASK}{sep}{tail}" if tail else _MASK


def safe_error(exc_or_text, limit=200):
    return _PATH_RE.sub(_mask_path, str(exc_or_text))[:limit]
