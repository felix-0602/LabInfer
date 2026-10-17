import numpy as np
import pytest

from app.models import uncertainty as u


def test_ols_recovers_true_slope_within_ci():
    rng = np.random.default_rng(42)
    c = np.linspace(0, 2.0, 7)
    A = 0.4 * c + 0.002 + rng.normal(0, 0.002, size=len(c))
    fit = u.ols_fit(c, A)
    ci = u.slope_ci(fit)
    assert ci[0] <= 0.4 <= ci[1]
    assert fit["r2"] > 0.999
    assert fit["n"] == 7


def test_inverse_predict_covers_truth():
    rng = np.random.default_rng(7)
    c = np.linspace(0, 2.0, 7)
    A = 0.4 * c + 0.002 + rng.normal(0, 0.002, size=len(c))
    fit = u.ols_fit(c, A)
    covered = 0
    draws = 60
    for _ in range(draws):
        c_true = 0.5
        y0 = 0.4 * c_true + 0.002 + float(rng.normal(0, 0.002))
        c_hat, u95 = u.inverse_predict(fit, y0)
        covered += int(abs(c_hat - c_true) <= u95)
    # 逆推 t 区间在 n=7 小样本下为近似区间，覆盖率略低于名义 95%，阈值取 80%
    assert covered >= 0.8 * draws


def test_grubbs_detects_injected_outlier():
    rng = np.random.default_rng(3)
    v = list(rng.normal(0, 0.01, size=7))
    clean = u.grubbs_test(v)
    assert not clean["outlier"]
    v2 = v[:]
    v2[3] += 0.1
    dirty = u.grubbs_test(v2)
    assert dirty["outlier"]
    assert dirty["index"] == 3


def test_arrhenius_transform_roundtrip_slope_sign():
    from app.models.base import ArrheniusModel
    m = ArrheniusModel()
    T = [20.0, 30.0, 40.0, 50.0, 60.0]
    Ea_true = 52.0  # kJ/mol
    R = u.R_GAS / 1000.0
    import math
    t = [math.exp((Ea_true / R) * (1.0 / (x + 273.15)) - 20.0) for x in T]
    fit = m.fit(T, t)
    assert fit["derived"]["Ea_kJ_per_mol"] == pytest.approx(Ea_true, rel=1e-6)
    lo, hi = fit["derived"]["Ea_ci95"]
    assert lo <= Ea_true <= hi
