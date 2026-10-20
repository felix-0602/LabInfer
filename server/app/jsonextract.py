"""两段式输出协议的 JSON 提取：纯 JSON 直解优先，fenced 次之，最后按出现位置平衡扫描。"""

import json


def extract_json(text: str):
    """从「人话 + 纯 JSON」混合输出中提取第一个 JSON 对象或数组。失败返回 None。"""
    if not text:
        return None
    obj = _try_loads(text.strip())          # 模型裸输出整段 JSON 的情形（glm-5.3-flash 现状）
    if obj is not None:
        return obj
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
    # 按出现位置取第一个配平的 JSON，对象与数组谁先出现取谁。旧实现按类型先扫 [ 再扫 {，
    # 裸 JSON 对象会被对象内部的嵌套数组偷走（M2「识别结果缺少 axes」的根因）。
    closers = {"{": "}", "[": "]"}
    for i, ch in enumerate(text):
        closer = closers.get(ch)
        if closer is None:
            continue
        end = _scan_balanced(text, i, ch, closer)
        if end is not None:
            obj = _try_loads(text[i:end + 1])
            if isinstance(obj, (list, dict)):
                return obj
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
