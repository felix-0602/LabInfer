"""M2 图表识别：VLM 读坐标轴刻度、轴类型、轴标题、图例与图表语义。只负责「读」，不做数值换算。

调用方式与 M1（app/vlm.py）一致：图片压缩到长边 1568px 后发给 settings.vlm_model。
VLM 看到的是压缩图，返回的像素坐标在这里按比例还原成原图像素。
图与实验是否同类（intent）由 assess_intent 用确定性规则比对，判断不交给模型。
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
   没有图例时按可见曲线逐条列出，label 填 ""。
6. chart：读出这张图本身的语义，全部来自轴标签、图例、图题里看得见的文字，读不出就填 null：
   {"type":"titration_curve"|"calibration_curve"|"gran_plot"|"spectra"|"other",
    "x_quantity":横轴量的名称（原样抄）,"y_quantity":纵轴量名称,
    "titrant":滴定剂名称或 null,"analyte":被测物名称或 null}。"""

# ---- 意图裁决（确定性）：“这张图”对“这个实验”能不能进对比 -------------------------------
# 只匹配轴标签/图例里看得见的字面，全部小写子串匹配；规则可测，判断不交给模型。

_X_VOLUME = ("volume", "counts", "体积", "滴定", "v(", " v ", "ml", "mass", "质量", "滴定剂")
_Y_PH = ("ph",)
_Y_EMF = ("e.m.f", "emf", "mv", "电位", "potential", "毫伏", "mv)")
_GRAN = ("gran", "10^-ph", "10ph", "(v0+ve)·10")
_ACID = ("hcl", "盐酸", "hydrochloric")
_SIGNAL = ("a", "absorbance", "吸光度", "signal", "荧光", "fluorescence", "峰")
_CONC = ("c", "concentration", "浓度")


def _hit(text: str, keys) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keys)


def assess_intent(chart: dict | None, ctx: dict) -> dict:
    """返回 {verdict, reasons}。verdict 三档：
    same 可直接对比；related 口径不同（讲解参照可用，按轴叠加要谨慎）；different 不同实验。"""
    if not isinstance(chart, dict) or not chart.get("type") or chart.get("type") == "other":
        return {"verdict": "related",
                "reasons": ["图上看不出曲线的类型（轴标签可能没写量的名称），不能确认与你的实验同类。"
                            "核对无误后仍可加入，对比时留意口径。"]}
    x = str(chart.get("x_quantity") or "")
    y = str(chart.get("y_quantity") or "")
    titrant = str(chart.get("titrant") or "")
    ctype = chart["type"]

    if ctx.get("model") == "titration_standardization":
        if ctype == "gran_plot" or _hit(y, _GRAN):
            return {"verdict": "related",
                    "reasons": ["这是 Gran 函数图——电位滴定数据的另一种画法，不是 pH 对体积的曲线。",
                                "可作讲解参照（讲阶里「不用指示剂判终点」用的就是它），不能进终点叠图。"]}
        if not _hit(x, _X_VOLUME):
            return {"verdict": "different",
                    "reasons": [f"横轴是「{x or '未知量'}」，不是滴定剂的体积——和滴定实验对不上，"
                                "加入对比没有意义。"]}
        if _hit(y, _Y_EMF):
            return {"verdict": "related",
                    "reasons": ["纵轴是电位（e.m.f./mV），不是 pH——这是电位滴定，你的实验在科研里的做法。",
                                "同一件事的科研级曲线：讲解与答辩引用它很有说服力，但不能按 pH 轴直接叠图。"]}
        if not _hit(y, _Y_PH):
            return {"verdict": "related",
                    "reasons": [f"纵轴是「{y or '未知量'}」，不是 pH。只有 pH 对体积的曲线能直接和你的终点叠加。"]}
        if titrant and not _hit(titrant, _ACID):
            return {"verdict": "related",
                    "reasons": [f"滴定剂是「{titrant}」，不是盐酸。曲线形状相似，但计量点位置不同，"
                                "叠加前要意识到口径差异。"]}
        return {"verdict": "same",
                "reasons": ["pH 对滴定体积的滴定曲线，且滴定剂为盐酸体系——与你的实验同类，可直接对比。",
                            "加入后 M4 会把它和你的终点换算到同一坐标（滴定分数）再叠加。"]}
    # 其余模型（线性标定类）
    if ctype == "calibration_curve" or (_hit(y, _SIGNAL) and _hit(x, _CONC)):
        return {"verdict": "same", "reasons": ["浓度对信号的标准曲线，与你的实验同类，可直接对比。"]}
    return {"verdict": "related",
            "reasons": [f"图类型读作「{ctype}」，不是标准曲线。核对口径后再决定是否加入。"]}


def _image_size(data: bytes) -> tuple[int, int]:
    from PIL import Image
    return Image.open(io.BytesIO(data)).size


def _scale_px(px, k: float) -> list[float]:
    return [round(float(px[0]) * k, 1), round(float(px[1]) * k, 1)]


def _sanitize_chart(obj: dict) -> dict | None:
    c = obj.get("chart")
    if not isinstance(c, dict):
        return None
    return {
        "type": str(c.get("type") or "other"),
        "x_quantity": str(c.get("x_quantity") or ""),
        "y_quantity": str(c.get("y_quantity") or ""),
        "titrant": c.get("titrant") if isinstance(c.get("titrant"), str) and c.get("titrant") else None,
        "analyte": c.get("analyte") if isinstance(c.get("analyte"), str) and c.get("analyte") else None,
    }


def normalize_detection(obj: dict, k: float, ctx: dict | None = None) -> dict:
    """把 VLM 输出整理成 FigureDetection（不含 figure_id / engine），像素乘 k 还原到原图。

    结构不可用（缺坐标轴、两个轴都没有可用刻度）时抛 ValueError，由路由转 503。
    带 ctx 时附 intent（0.9.0 可选字段）：确定性规则比对图与实验是否同类，见 assess_intent。
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

    det = {"schema_version": CONTRACT_VERSION, "plot_area": plot_area, "axes": axes,
           "calibration": calibration, "series": series, "warnings": warnings}
    chart = _sanitize_chart(obj)
    if ctx is not None:
        intent = assess_intent(chart, ctx)
        intent["chart"] = chart            # 裁决所依据的事实（VLM 读到的图表语义）一并下发
        det["intent"] = intent
    return det


async def detect_figure(image_bytes: bytes, ctx: dict | None = None) -> dict:
    jpeg = compress_image(image_bytes)
    w0, _ = _image_size(image_bytes)
    w1, _ = _image_size(jpeg)
    k = w0 / w1
    messages = [
        {"role": "system", "content": FIGURE_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": "识别这张曲线图，按系统规则输出 JSON："
                                     '{"plot_area":{...},"axes":{"x":{...},"y":{...}},'
                                     '"series":[...],"chart":{...}}'},
            {"type": "image_url", "image_url": {"url": _data_uri(jpeg)}},
        ]},
    ]
    raw = await chat(messages, model=settings.vlm_model)
    det = normalize_detection(extract_json(raw), k, ctx)
    det["engine"] = {"vlm": settings.vlm_model, "cached": False}
    return det
