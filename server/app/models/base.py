"""模型注册表。新增模型 = 新增一个子类 + 注册，路由与契约不变（contracts 0.3.0）。"""

import math

from . import uncertainty as u


class AnalysisModel:
    id: str = ""
    x_role: str = ""
    y_role: str = ""
    optional_roles: list[str] = []
    simulatable_params: list[str] = []
    formula: str = ""

    def transform(self, x: list[float], y: list[float]):
        return x, y

    def fit(self, x: list[float], y: list[float]) -> dict:
        f = u.ols_fit(*self.transform(x, y))
        f["model"] = self.id
        f["derived"] = self.derived(f)
        return f

    def derived(self, fit: dict) -> dict:
        ci = u.slope_ci(fit)
        return {"slope_ci95": [round(ci[0], 6), round(ci[1], 6)]}

    def predict(self, fit: dict, x: float) -> float:
        return fit["slope"] * x + fit["intercept"]


class LinearCalibrationModel(AnalysisModel):
    id = "linear_calibration"
    x_role = "concentration"
    y_role = "signal"
    optional_roles = ["sample_volume", "dilution_factor"]
    simulatable_params = ["dilution_factor", "sample_volume"]
    formula = "A = b·c + a；ρ = (A − a)/b × (V定容/V取样) × dil"

    def derived(self, fit: dict) -> dict:
        out = super().derived(fit)
        out["sensitivity"] = fit["slope"]
        return out


class ArrheniusModel(AnalysisModel):
    id = "arrhenius"
    x_role = "temperature"
    y_role = "time"
    optional_roles = []
    simulatable_params = ["temperature"]
    formula = "ln(1/t) = ln A − Ea/R · 1/T"

    def transform(self, x, y):
        xs = [1.0 / (t + 273.15) for t in x]
        ys = [math.log(1.0 / t) for t in y]
        return xs, ys

    def derived(self, fit: dict) -> dict:
        ci = u.slope_ci(fit)
        out = {
            "Ea_kJ_per_mol": -fit["slope"] * u.R_GAS / 1000.0,
            "Ea_ci95": [
                -ci[1] * u.R_GAS / 1000.0,
                -ci[0] * u.R_GAS / 1000.0,
            ],
        }
        return out


class TitrationStandardizationModel(AnalysisModel):
    """酸碱滴定（演示案例）：基准物质标定 + 样品含量。
    标定段：V(HCl) = k·m(基准)，过原点拟合；逐份 c_i = 2m/(M·V) 后取平均。
    测定段：w(Na₂O) = c̄·V·M(Na₂O)/2 × (V容/V移) ÷ m样 ×100%。"""

    id = "titration_standardization"
    x_role = "mass"
    y_role = "volume"
    optional_roles = ["sample_mass"]
    simulatable_params = ["titrant_volume_delta"]
    formula = ("c(HCl) = 2m/(M(Na₂CO₃)·V)；"
               "w(Na₂O) = c̄·V·M(Na₂O)/2 × V容/V移 ÷ m样 ×100%")

    # 过原点回归：滴定体积与基准物质质量成正比（GB/T 601-2016 称样量设计的前提）
    def fit(self, x: list[float], y: list[float], molar_mass: float = 105.99) -> dict:
        n = len(x)
        if n < 3:
            raise ValueError("标定至少需要 3 份平行")
        sxy = sum(a * b for a, b in zip(x, y))
        sxx = sum(a * a for a in x)
        if sxx == 0:
            raise ValueError("称样量全为 0，无法回归")
        k = sxy / sxx
        resid = [b - k * a for a, b in zip(x, y)]
        ss_res = sum(r * r for r in resid)
        ss_tot = sum(b * b for b in y)
        f = {
            "n": n, "dof": n - 1,
            "slope": k, "intercept": 0.0,
            "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
            "residuals": resid,
            "molar_mass": molar_mass,
        }
        f["model"] = self.id
        f["derived"] = self.derived(f)
        return f

    def derived(self, fit: dict) -> dict:
        return {"c_regression": 2.0 / (fit["molar_mass"] * fit["slope"] / 1000.0)}

    def conc(self, m_g: float, v_ml: float, molar_mass: float = 105.99) -> float:
        """单份标定浓度 c(HCl) = 2m/(M·V)，等价于 GB/T 601-2016 的 m·1000/(V·52.994)。"""
        return 2.0 * m_g / (molar_mass * v_ml / 1000.0)

    def w_na2o(self, c: float, v_ml: float, m_sample_g: float,
               molar_mass: float = 61.979, stock_ml: float = 250.0,
               aliquot_ml: float = 25.0) -> float:
        """总碱度（以 Na₂O 计，质量分数 %）。滴定反应 Na₂CO₃+2HCl，故 n(Na₂O)=n(HCl)/2。"""
        return (c * v_ml / 1000.0 / 2.0 * molar_mass * stock_ml / aliquot_ml
                / m_sample_g * 100.0)

    def predict(self, fit: dict, x: float) -> float:
        return fit["slope"] * x  # 过原点：V = k·m


def rel_avg_dev(values: list[float]) -> float:
    """相对平均偏差（教学口径）：mean|x−x̄|/x̄。"""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    return sum(abs(v - mean) for v in values) / len(values) / mean


REGISTRY: dict[str, AnalysisModel] = {
    m.id: m for m in (LinearCalibrationModel(), ArrheniusModel(),
                      TitrationStandardizationModel())
}
