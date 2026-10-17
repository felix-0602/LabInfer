"""标曲回归、逆推不确定度、格拉布斯检验。纯函数，无 IO。"""

import math

import numpy as np
from scipy import stats

R_GAS = 8.314462618  # J/(mol·K)


def ols_fit(x, y) -> dict:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = int(len(x))
    if n < 3:
        raise ValueError("拟合至少需要 3 个点")
    slope, intercept = np.polyfit(x, y, 1)
    yhat = slope * x + intercept
    resid = y - yhat
    sse = float((resid ** 2).sum())
    sst = float(((y - y.mean()) ** 2).sum())
    sxx = float(((x - x.mean()) ** 2).sum())
    dof = n - 2
    s_e = math.sqrt(sse / dof)
    return {
        "n": n,
        "dof": dof,
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": 1.0 - sse / sst if sst > 0 else float("nan"),
        "s_e": s_e,
        "sxx": sxx,
        "xbar": float(x.mean()),
        "residuals": resid.tolist(),
    }


def slope_ci(fit: dict, conf: float = 0.95) -> list[float]:
    t = float(stats.t.ppf(0.5 + conf / 2, fit["dof"]))
    half = t * fit["s_e"] / math.sqrt(fit["sxx"])
    return [fit["slope"] - half, fit["slope"] + half]


def inverse_predict(fit: dict, y0: float, m: int = 1, conf: float = 0.95):
    """经典逆推（inverse prediction）：由吸光度反推浓度及扩展不确定度。"""
    a, b = fit["intercept"], fit["slope"]
    if b == 0:
        raise ValueError("斜率为 0，无法反推")
    c_hat = (y0 - a) / b
    n, s_e, sxx = fit["n"], fit["s_e"], fit["sxx"]
    ybar = a + b * fit["xbar"]
    u = (s_e / abs(b)) * math.sqrt(1.0 / m + 1.0 / n + (y0 - ybar) ** 2 / (b ** 2 * sxx))
    t = float(stats.t.ppf(0.5 + conf / 2, fit["dof"]))
    return float(c_hat), float(t * u)


def grubbs_test(values, alpha: float = 0.05) -> dict:
    """单离群格拉布斯检验（双侧）。返回最可疑点及其统计量与 p 值近似。"""
    v = np.asarray(values, dtype=float)
    n = int(len(v))
    if n < 3:
        return {"n": n, "index": None, "G": None, "G_crit": None, "outlier": False, "p": None}
    s = float(v.std(ddof=1))
    if s == 0:
        return {"n": n, "index": None, "G": 0.0, "G_crit": None, "outlier": False, "p": 1.0}
    dev = np.abs(v - v.mean())
    idx = int(dev.argmax())
    G = float(dev[idx] / s)
    t = float(stats.t.ppf(1 - alpha / (2 * n), n - 2))
    G_crit = ((n - 1) / math.sqrt(n)) * math.sqrt(t * t / (n - 2 + t * t))
    # 由 G 反解 t 求 p 值近似
    denom = (n - 1) ** 2 - n * G * G
    if denom > 0:
        t_obs = G * math.sqrt(n * (n - 2) / denom)
        p = float(2 * stats.t.sf(t_obs, n - 2))
    else:
        p = 0.0
    return {"n": n, "index": idx, "G": G, "G_crit": G_crit, "outlier": bool(G > G_crit), "p": p}
