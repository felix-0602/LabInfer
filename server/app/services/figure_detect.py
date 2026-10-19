"""M2 图表识别：VLM 读坐标轴刻度、轴类型、轴标题和图例。只负责「读」，不做数值换算。

调用方式与 M1（app/vlm.py）一致：图片压缩到长边 1568px 后发给 settings.vlm_model。
VLM 看到的是压缩图，返回的像素坐标在这里按比例还原成原图像素。
"""

import io

from ..config import CONTRACT_VERSION, settings
from ..jsonextract import extract_json
from ..llm import chat
from ..vlm import _data_uri, compress_image
from .calibration import suggest_calibration

FIGURE_SYSTEM = """你是论文图表识别助手。用户给你一张科研论文里的曲线图截图。
只做读取，不做任何数值换算或推断，规则：
1. 只输出一个 JSON 对象，不要多余文字。
2. 像素坐标以图片左上角为原点，u 向右、v 向下，单位是你看到的这张图的像素，写作 [u, v]。
3. plot_area：绘图区边框 {"u0","v0","u1","v1"}（左、上、右、下）。
4. axes.x / axes.y：{"label":轴标题,"unit":单位或"","scale":"linear"|"log10","ticks":[{"px":[u,v],"value":数值,"confidence":0~1}]}。
   ticks 是刻度线在轴上的位置和它标注的数值；数值看不清就省略该刻度，不许猜。
5. series：图例里的每条曲线 {"id":"A","label":图例文字,"color":"#rrggbb","marker":"o"|"x"|"s"|"^"|"line"|...,"confidence":0~1}。
   没有图例时按可见曲线逐条列出，label 填 ""。"""


def _image_size(data: bytes) -> tuple[int, int]:
    from PIL import Image
    return Image.open(io.BytesIO(data)).size


def _scale_px(px, k: float) -> list[float]:
    return [round(float(px[0]) * k, 1), round(float(px[1]) * k, 1)]


def normalize_detection(obj: dict, k: float) -> dict:
    """把 VLM 输出整理成 FigureDetection（不含 figure_id / engine），像素乘 k 还原到原图。

    结构不可用（缺坐标轴、两个轴都没有可用刻度）时抛 ValueError，由路由转 503。
    """
    if not isinstance(obj, dict) or not isinstance(obj.get("axes"), dict):
        raise ValueError("识别结果缺少 axes")
    axes = {}
    for axis in ("x", "y"):
        a = obj["axes"].get(axis) or {}
        ticks = []
        for t in a.get("ticks") or []:
            try:
                value = float(t["value"])
                px = _scale_px(t["px"], k)
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            ticks.append({"px": px, "value": value,
                          "confidence": float(t.get("confidence") or 0.0)})
        scale = a.get("scale") if a.get("scale") in ("linear", "log10") else "linear"
        axes[axis] = {"label": str(a.get("label") or ""), "unit": str(a.get("unit") or ""),
                      "scale": scale, "ticks": ticks}

    calibration, warnings = suggest_calibration(axes)
    if calibration["x"] is None and calibration["y"] is None:
        raise ValueError("两个坐标轴都没有识别到可用刻度")

    pa = obj.get("plot_area")
    try:
        plot_area = {key: round(float(pa[key]) * k, 1) for key in ("u0", "v0", "u1", "v1")}
    except (KeyError, TypeError, ValueError):
        plot_area = None
        warnings.append("未识别到绘图区边框，自动提取将在整张图上进行")

    series = []
    for i, s in enumerate(obj.get("series") or []):
        if not isinstance(s, dict):
            continue
        series.append({"id": str(s.get("id") or chr(ord("A") + i)),
                       "label": str(s.get("label") or ""),
                       "color": s.get("color"),
                       "marker": s.get("marker"),
                       "confidence": float(s.get("confidence") or 0.0)})
    if not series:
        warnings.append("未识别到曲线或图例，请改用手动点取")

    return {"schema_version": CONTRACT_VERSION, "plot_area": plot_area, "axes": axes,
            "calibration": calibration, "series": series, "warnings": warnings}


async def detect_figure(image_bytes: bytes) -> dict:
    jpeg = compress_image(image_bytes)
    w0, _ = _image_size(image_bytes)
    w1, _ = _image_size(jpeg)
    k = w0 / w1
    messages = [
        {"role": "system", "content": FIGURE_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": "识别这张曲线图，按系统规则输出 JSON："
                                     '{"plot_area":{...},"axes":{"x":{...},"y":{...}},"series":[...]}'},
            {"type": "image_url", "image_url": {"url": _data_uri(jpeg)}},
        ]},
    ]
    raw = await chat(messages, model=settings.vlm_model)
    det = normalize_detection(extract_json(raw), k)
    det["engine"] = {"vlm": settings.vlm_model, "cached": False}
    return det
