"""两段式输出协议的 JSON 提取：fenced 优先，其次 string-aware 平衡括号扫描。"""

import json


def extract_json(text: str):
    """从「人话 + 纯 JSON」混合输出中提取第一个 JSON 对象或数组。失败返回 None。"""
    if not text:
        return None
    for chunk in _fenced_blocks(text):
        obj = _try_loads(chunk)
        if obj is not None:
            return obj
    return _balanced_scan(text)


def _fenced_blocks(text: str):
    out = []
    parts = text.split("```")
    for i in range(1, len(parts), 2):
        block = parts[i]
        if block.startswith("json"):
            block = block[4:]
        out.append(block.strip())
    return out


def _try_loads(s: str):
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None


def _balanced_scan(text: str):
    for opener, closer in (("[", "]"), ("{", "}")):
        start = 0
        while True:
            i = text.find(opener, start)
            if i < 0:
                break
            end = _scan_balanced(text, i, opener, closer)
            if end is not None:
                obj = _try_loads(text[i:end + 1])
                if isinstance(obj, (list, dict)):
                    return obj
            start = i + 1
    return None


def _scan_balanced(text: str, begin: int, opener: str, closer: str):
    depth = 0
    in_str = False
    esc = False
    for i in range(begin, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return i
    return None
