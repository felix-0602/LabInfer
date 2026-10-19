"""M1 视觉识别：glm-5.3-flash，两段式——版面分析找表格 → 逐表裁剪识别 → 合并行。
图片压缩到长边 1568px，识别结果即 Dataset 行。"""

import base64
import io

from .config import CONTRACT_VERSION, settings
from .jsonextract import extract_json
from .llm import LlmError, chat
from .prompts import RECORD_SYSTEM

_MAX_EDGE = 1568

DETECT_TABLES_SYSTEM = """你是图片版面分析器。找出图片里每一个独立的表格区域（有横竖线或行列对齐结构），
包括标题写着「续表」的小表——续表也单独输出一个 bbox。
表格上方紧邻的标题行和备注（例如「1. HCl 溶液的标定」「2. 碱灰总碱度的测定（m=1.5919 g）」）
属于这张表的一部分，必须框进同一个 bbox。页眉、表单抬头（专业/学号填空行）不算表格。
只输出 JSON：{"tables":[{"bbox":[x1,y1,x2,y2]}]}，坐标为归一化整数 0-1000（相对整图宽高，原点左上），
按从上到下排列。图中没有表格时输出 {"tables":[]}。不要输出任何多余文字。"""

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


async def detect_tables(jpeg: bytes) -> list[tuple[float, float, float, float]]:
    """版面分析：返回每张表的归一化 (0..1) 边界框，从上到下。失败或不可信时返回 []，
    调用方回退整页单次识别。"""
    try:
        raw = await chat(
            [{"role": "system", "content": DETECT_TABLES_SYSTEM},
             {"role": "user", "content": [
                 {"type": "text", "text": "找出图中全部表格的 bbox。"},
                 {"type": "image_url", "image_url": {"url": _data_uri(jpeg)}},
             ]}], model=settings.vlm_model, temperature=0, timeout=120)
    except (LlmError, ValueError):
        return []
    obj = extract_json(raw)
    # extract_json 的括号扫描可能剥掉外壳直接返回内层数组，两种形状都认
    tables = obj.get("tables") if isinstance(obj, dict) else (obj if isinstance(obj, list) else [])
    boxes = []
    for t in tables:
        if not isinstance(t, dict):
            continue
        try:
            x1, y1, x2, y2 = (float(v) for v in t["bbox"])
        except (KeyError, TypeError, ValueError):
            continue
        x1, y1, x2, y2 = max(0.0, x1), max(0.0, y1), min(1000.0, x2), min(1000.0, y2)
        x1, x2 = min(x1, x2) / 1000, max(x1, x2) / 1000
        y1, y2 = min(y1, y2) / 1000, max(y1, y2) / 1000
        if (x2 - x1) * (y2 - y1) >= 0.005 and (x2 - x1) >= 0.2 and (y2 - y1) >= 0.02:
            boxes.append((x1, y1, x2, y2))
    boxes.sort(key=lambda b: b[1])
    return boxes


async def _recognize_region(jpeg: bytes, ctx: dict,
                            table_no: int | None = None, n_tables: int = 1) -> list[dict]:
    """识别单张（裁剪后的）表格图，返回行列表（不含全局 id）。"""
    columns = ctx["variables"]["columns"]
    col_spec = [{"key": c["key"], "role": c["role"], "unit": c.get("unit", "")} for c in columns]
    hint = (f"这是同一页记录中第 {table_no}/{n_tables} 张表格的裁剪图，只识别这张表的数据行，"
            if table_no else "")
    hint += "与列定义不对应的行（如平均值、偏差、相对平均偏差等汇总行）直接跳过，不要硬套成 null。"
    user = (f"实验：{ctx.get('name')}。列定义：{col_spec}\n"
            f"{hint}识别图里的记录表，按系统规则输出 JSON："
            f'{{"rows":[{{"series":...,"values":{{...}},"confidence":{{...}}}}]}}')
    messages = [
        {"role": "system", "content": RECORD_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": user},
            {"type": "image_url", "image_url": {"url": _data_uri(jpeg)}},
        ]},
    ]
    raw = await chat(messages, model=settings.vlm_model, timeout=120)
    obj = extract_json(raw)
    if isinstance(obj, list):                    # 模型常无视格式约定直接给行数组
        obj = {"rows": obj}
    rows = []
    for r in (obj or {}).get("rows", []):
        if not isinstance(r, dict):
            continue
        rows.append({
            "series": normalize_series(r.get("series") or "std"),
            "values": r.get("values") or {},
            "confidence": r.get("confidence") or {},
            "verified": False,
        })
    return rows


async def recognize_record(image_bytes: bytes, ctx: dict) -> dict:
    """返回 Dataset dict（不含 id/image_ref，由路由层补）。

    两段式：版面分析找出多张表 → 逐表裁剪识别 → 合并行；整页只有一张表或
    版面分析失败时，退回整页单次识别（多表记录页整页识别会漏表，实测见
    scripts/live_check）。"""
    from PIL import Image

    jpeg = compress_image(image_bytes)
    rows: list[dict] = []
    boxes = await detect_tables(jpeg)
    if len(boxes) >= 2:
        img = Image.open(io.BytesIO(jpeg))
        W, H = img.size
        pad_x, pad_top, pad_bottom = 0.015, 0.045, 0.02   # 上边多留：标题行/备注常在表格上方
        for i, (x1, y1, x2, y2) in enumerate(boxes, start=1):
            crop = img.crop((
                max(0, int((x1 - pad_x) * W)), max(0, int((y1 - pad_top) * H)),
                min(W, int((x2 + pad_x) * W)), min(H, int((y2 + pad_bottom) * H))))
            buf = io.BytesIO()
            crop.save(buf, format="JPEG", quality=92)
            try:
                rows += await _recognize_region(buf.getvalue(), ctx,
                                                table_no=i, n_tables=len(boxes))
            except (LlmError, ValueError):
                continue                           # 单张表失败不拖垮整页
    if not rows:
        rows = await _recognize_region(jpeg, ctx)

    rows = [r for r in rows
            if any(v is not None and v != "" for v in r["values"].values())]   # 丢弃全空行
    rows_out = []
    for i, r in enumerate(rows, start=1):
        rows_out.append({
            "id": f"p{i}",
            "series": r["series"],
            "values": r["values"],
            "confidence": r["confidence"],
            "verified": False,
        })
    return {
        "schema_version": CONTRACT_VERSION,
        "source": "my_experiment",
        "meta": {"title": f"{ctx.get('name')} 记录识别", "doi": None, "figure": None},
        "columns": [{"key": c["key"], "name": c["key"], "unit": c.get("unit", "")}
                    for c in ctx["variables"]["columns"]],
        "rows": rows_out,
    }
