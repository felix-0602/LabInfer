"""M1 视觉识别：glm-5.3-flash，图片压缩到长边 1568px，识别结果即 Dataset 行。"""

import base64
import io

from .config import CONTRACT_VERSION, settings
from .jsonextract import extract_json
from .llm import chat
from .prompts import RECORD_SYSTEM

_MAX_EDGE = 1568

# 模型常不按枚举写 series（全角冒号、中文前缀、裸「标定」），在边界统一归一到契约枚举
_SERIES_ALIASES = {"标定": "std", "标准": "std", "标准系列": "std", "空白": "blank"}
_SERIES_PREFIXES = ("sample", "样品", "试样", "样本")


def normalize_series(s: str) -> str:
    s = (s or "").strip()
    if s in ("std", "blank", "qc:crm", "qc:spike"):
        return s
    if s in _SERIES_ALIASES:
        return _SERIES_ALIASES[s]
    if s.startswith("qc:"):
        return "qc:crm"
    for prefix in _SERIES_PREFIXES:
        for colon in (":", "："):
            head = prefix + colon
            if s.lower().startswith(head):
                name = s[len(head):].strip().strip("：: ")
                return f"sample:{name}" if name else "sample:样品"
    return s


def compress_image(data: bytes) -> bytes:
    from PIL import Image
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if max(img.size) > _MAX_EDGE:
        img.thumbnail((_MAX_EDGE, _MAX_EDGE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _data_uri(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")


async def recognize_record(image_bytes: bytes, ctx: dict) -> dict:
    """返回 Dataset dict（不含 id/image_ref，由路由层补）。"""
    columns = ctx["variables"]["columns"]
    col_spec = [{ "key": c["key"], "role": c["role"], "unit": c.get("unit", "")} for c in columns]
    user = (f"实验：{ctx.get('name')}。列定义：{col_spec}\n"
            f"识别照片里的记录表，按系统规则输出 JSON："
            f'{{"rows":[{{"series":...,"values":{{...}},"confidence":{{...}}}}]}}')
    messages = [
        {"role": "system", "content": RECORD_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": user},
            {"type": "image_url", "image_url": {"url": _data_uri(compress_image(image_bytes))}},
        ]},
    ]
    raw = await chat(messages, model=settings.vlm_model, timeout=120)
    obj = extract_json(raw)
    if isinstance(obj, list):                    # 模型常无视格式约定直接给行数组
        obj = {"rows": obj}
    rows_out = []
    for i, r in enumerate((obj or {}).get("rows", []), start=1):
        if not isinstance(r, dict):
            continue
        rows_out.append({
            "id": f"p{i}",
            "series": normalize_series(r.get("series") or "std"),
            "values": r.get("values") or {},
            "confidence": r.get("confidence") or {},
            "verified": False,
        })
    return {
        "schema_version": CONTRACT_VERSION,
        "source": "my_experiment",
        "meta": {"title": f"{ctx.get('name')} 记录识别", "doi": None, "figure": None},
        "columns": [{"key": c["key"], "name": c["key"], "unit": c.get("unit", "")}
                    for c in columns],
        "rows": rows_out,
    }
