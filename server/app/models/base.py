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


REGISTRY: dict[str, AnalysisModel] = {
    m.id: m for m in (LinearCalibrationModel(), ArrheniusModel())
}
