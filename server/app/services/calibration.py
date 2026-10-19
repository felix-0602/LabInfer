"""M2 坐标换算与校准残差。确定性代码，公式见 docs/contracts.md「坐标换算」。

坐标轴假设水平、竖直、无旋转：x 只用像素 u，y 只用像素 v。
"""

import math

_PX_INDEX = {"x": 0, "y": 1}
SCALES = ("linear", "log10")


class CalibrationError(ValueError):
    """校准无法用于换算（参考点重合、对数轴 a ≤ 0 等），路由层转 422。"""


def _axis_params(axis: str, cal: dict) -> tuple[str, float, float, float, float]:
    """校验单轴校准，返回 (scale, 像素1, 数值1, 像素2, 数值2)；数值已按刻度类型变换（log10 取对数）。"""
    if not isinstance(cal, dict):
        raise CalibrationError(f"{axis} 轴缺少校准")
    scale = cal.get("scale", "linear")
    if scale not in SCALES:
        raise CalibrationError(f"{axis} 轴 scale 只能是 linear 或 log10: {scale!r}")
    i = _PX_INDEX[axis]
    try:
        c1 = float(cal["p1"]["px"][i])
        a1 = float(cal["p1"]["value"])
        c2 = float(cal["p2"]["px"][i])
        a2 = float(cal["p2"]["value"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise CalibrationError(f"{axis} 轴参考点不完整（需要 p1/p2 的 px 与 value）") from e
    if not all(math.isfinite(t) for t in (c1, a1, c2, a2)):
        raise CalibrationError(f"{axis} 轴参考点含非有限数")
    if c1 == c2:
        raise CalibrationError(f"{axis} 轴两个参考点的像素坐标相同，无法换算")
    if scale == "log10":
        if a1 <= 0 or a2 <= 0:
            raise CalibrationError(f"{axis} 轴为对数轴，参考点数值必须大于 0")
        a1, a2 = math.log10(a1), math.log10(a2)
    if a1 == a2:
        raise CalibrationError(f"{axis} 轴两个参考点的数值相同，无法换算")
    return scale, c1, a1, c2, a2


def validate_calibration(calibration: dict) -> None:
    if not isinstance(calibration, dict):
        raise CalibrationError("calibration 必须是对象")
    for axis in ("x", "y"):
        _axis_params(axis, calibration.get(axis))


def px_to_value(axis: str, cal: dict, c: float) -> float:
    """像素坐标（x 轴传 u，y 轴传 v）→ 坐标轴数值。"""
    scale, c1, a1, c2, a2 = _axis_params(axis, cal)
    t = a1 + (c - c1) * (a2 - a1) / (c2 - c1)
    return 10 ** t if scale == "log10" else t


def value_to_px(axis: str, cal: dict, value: float) -> float:
    """坐标轴数值 → 像素坐标，用于残差反算。对数轴上 value ≤ 0 时抛 CalibrationError。"""
    scale, c1, a1, c2, a2 = _axis_params(axis, cal)
    if scale == "log10":
        if value <= 0:
            raise CalibrationError(f"{axis} 轴为对数轴，刻度数值必须大于 0")
        value = math.log10(value)
    return c1 + (value - a1) * (c2 - c1) / (a2 - a1)


def to_data(calibration: dict, px: list[float]) -> tuple[float, float]:
    return (px_to_value("x", calibration["x"], px[0]),
            px_to_value("y", calibration["y"], px[1]))


def _is_reference(tick: dict, cal: dict, i: int) -> bool:
    for p in ("p1", "p2"):
        ref = cal[p]
        if (float(tick["value"]) == float(ref["value"])
                and abs(float(tick["px"][i]) - float(ref["px"][i])) < 1e-9):
            return True
    return False


def residual_px(calibration: dict, axes: dict | None) -> float | None:
    """其余刻度按校准反算像素，与识别位置之差的均方根。没有其余刻度时为 None。

    axes 是 FigureDetection.axes（{x: {ticks: [...]}, y: {...}}）；参考点本身不计入。
    """
    if not axes:
        return None
    errs: list[float] = []
    for axis in ("x", "y"):
        cal = calibration[axis]
        i = _PX_INDEX[axis]
        for tick in (axes.get(axis) or {}).get("ticks") or []:
            try:
                value = float(tick["value"])
                actual = float(tick["px"][i])
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            if _is_reference(tick, cal, i):
                continue
            try:
                errs.append(value_to_px(axis, cal, value) - actual)
            except CalibrationError:
                continue
    if not errs:
        return None
    return round(math.sqrt(sum(e * e for e in errs) / len(errs)), 3)


def suggest_calibration(axes: dict) -> tuple[dict, list[str]]:
    """每个轴取相距最远的两个刻度作为校准建议。刻度不足的轴给 None 并附警告。"""
    out: dict = {}
    warnings: list[str] = []
    for axis in ("x", "y"):
        a = axes.get(axis) or {}
        i = _PX_INDEX[axis]
        ticks = [t for t in a.get("ticks") or [] if t.get("value") is not None]
        best = None
        for j in range(len(ticks)):
            for k in range(j + 1, len(ticks)):
                d = abs(ticks[k]["px"][i] - ticks[j]["px"][i])
                if d > 0 and ticks[k]["value"] != ticks[j]["value"] and (best is None or d > best[0]):
                    best = (d, ticks[j], ticks[k])
        if best is None:
            out[axis] = None
            warnings.append(f"{axis} 轴可用刻度不足 2 个，需要手动放置校准点")
            continue
        _, t1, t2 = best
        if t1["value"] > t2["value"]:
            t1, t2 = t2, t1
        out[axis] = {"scale": a.get("scale", "linear"),
                     "p1": {"px": list(t1["px"]), "value": t1["value"]},
                     "p2": {"px": list(t2["px"]), "value": t2["value"]}}
        if len(ticks) == 2:
            warnings.append(f"{axis} 轴只识别到 2 个刻度，无法用该轴计算残差")
    return out, warnings
