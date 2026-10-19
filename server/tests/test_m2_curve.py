import io
import math

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.config import settings
from app.main import create_app
from app.services.calibration import (CalibrationError, px_to_value, residual_px,
                                      suggest_calibration, to_data, validate_calibration,
                                      value_to_px)
from app.services.curve_extract import extract_points
from app.services.figure_detect import normalize_detection
from app.sqlstore import SqlStore
from app.storage import Store

# 合成图：绘图区 (100,50)-(500,350)；x 轴 u=100→0、u=500→10；y 轴 v=350→0、v=50→1
CAL = {
    "x": {"scale": "linear", "p1": {"px": [100, 350], "value": 0.0},
          "p2": {"px": [500, 350], "value": 10.0}},
    "y": {"scale": "linear", "p1": {"px": [100, 350], "value": 0.0},
          "p2": {"px": [100, 50], "value": 1.0}},
}
PLOT_AREA = {"u0": 100, "v0": 50, "u1": 500, "v1": 350}
RED = (214, 39, 40)
BLUE = (31, 119, 180)
MARKERS = [(2.0, 0.2), (4.0, 0.4), (6.0, 0.6), (8.0, 0.8)]


def _u(x):
    return 100 + x * 40


def _v(y):
    return 350 - y * 300


def _ticks(axis, values):
    if axis == "x":
        return [{"px": [_u(x), 350], "value": x, "confidence": 0.9} for x in values]
    return [{"px": [100, _v(y)], "value": y, "confidence": 0.9} for y in values]


DETECTION = {
    "plot_area": PLOT_AREA,
    "axes": {
        "x": {"label": "c", "unit": "mg/L", "scale": "linear", "ticks": _ticks("x", [0, 5, 10])},
        "y": {"label": "A", "unit": "", "scale": "linear", "ticks": _ticks("y", [0, 0.5, 1])},
    },
    "series": [
        {"id": "A", "label": "红点", "color": "#d62728", "marker": "o", "confidence": 0.9},
        {"id": "B", "label": "蓝线", "color": "#1f77b4", "marker": "line", "confidence": 0.9},
        {"id": "C", "label": "绿色", "color": "#2ca02c", "marker": "o", "confidence": 0.9},
    ],
}


def _synthetic_png() -> bytes:
    img = Image.new("RGB", (600, 400), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([100, 50, 500, 350], outline="black", width=2)
    for x, y in MARKERS:
        d.ellipse([_u(x) - 5, _v(y) - 5, _u(x) + 5, _v(y) + 5], fill=RED)
    # 蓝色直线 y = 0.03 x + 0.5，x 从 1 到 9，不压在红点上
    d.line([(_u(1), _v(0.53)), (_u(9), _v(0.77))], fill=BLUE, width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------- 换算 ----------

def test_linear_conversion_and_inverse():
    assert px_to_value("x", CAL["x"], 300) == pytest.approx(5.0)
    assert px_to_value("y", CAL["y"], 200) == pytest.approx(0.5)
    assert to_data(CAL, [180, 290]) == pytest.approx((2.0, 0.2))
    assert value_to_px("x", CAL["x"], 7.5) == pytest.approx(400)


def test_log10_conversion():
    cal = {"scale": "log10", "p1": {"px": [100, 0], "value": 1.0},
           "p2": {"px": [400, 0], "value": 1000.0}}
    assert px_to_value("x", cal, 200) == pytest.approx(10.0)
    assert px_to_value("x", cal, 250) == pytest.approx(10 ** 1.5)
    assert value_to_px("x", cal, 100.0) == pytest.approx(300)


@pytest.mark.parametrize("axis_cal", [
    # u1 = u2
    {"scale": "linear", "p1": {"px": [200, 0], "value": 0.0}, "p2": {"px": [200, 9], "value": 1.0}},
    # 对数轴 a ≤ 0
    {"scale": "log10", "p1": {"px": [100, 0], "value": 0.0}, "p2": {"px": [400, 0], "value": 10.0}},
    {"scale": "log10", "p1": {"px": [100, 0], "value": -1.0}, "p2": {"px": [400, 0], "value": 10.0}},
])
def test_invalid_calibration_raises(axis_cal):
    with pytest.raises(CalibrationError):
        validate_calibration({"x": axis_cal, "y": CAL["y"]})


def test_residual_px():
    axes = DETECTION["axes"]
    # 其余刻度恰好在线上：残差 0
    assert residual_px(CAL, axes) == pytest.approx(0.0)
    # x=5 的刻度偏 3px、y=0.5 的刻度偏 4px：RMS = sqrt((9+16)/2)
    shifted = {"x": {"ticks": [{"px": [303, 350], "value": 5}] + _ticks("x", [0, 10])},
               "y": {"ticks": [{"px": [100, 196], "value": 0.5}] + _ticks("y", [0, 1])}}
    assert residual_px(CAL, shifted) == pytest.approx(math.sqrt(12.5), abs=1e-3)


def test_residual_null_when_only_reference_ticks():
    axes = {"x": {"ticks": _ticks("x", [0, 10])}, "y": {"ticks": _ticks("y", [0, 1])}}
    assert residual_px(CAL, axes) is None
    assert residual_px(CAL, None) is None


def test_suggest_calibration_picks_farthest_ticks():
    cal, warnings = suggest_calibration(DETECTION["axes"])
    assert cal["x"]["p1"]["value"] == 0 and cal["x"]["p2"]["value"] == 10
    assert cal["y"]["p1"]["px"] == [100, 350] and cal["y"]["p2"]["value"] == 1
    assert warnings == []
    cal2, w2 = suggest_calibration({"x": {"ticks": _ticks("x", [0, 10])}, "y": {"ticks": []}})
    assert cal2["y"] is None and len(w2) == 2


def test_normalize_detection_rescales_pixels():
    obj = {"plot_area": {"u0": 50, "v0": 25, "u1": 250, "v1": 175},
           "axes": {"x": {"ticks": [{"px": [50, 175], "value": 0}, {"px": [250, 175], "value": 10}]},
                    "y": {"ticks": [{"px": [50, 175], "value": 0}, {"px": [50, 25], "value": 1}]}},
           "series": [{"label": "s", "color": "#000000"}]}
    det = normalize_detection(obj, 2.0)
    assert det["plot_area"] == PLOT_AREA
    assert det["calibration"]["x"]["p2"]["px"] == [500.0, 350.0]
    assert det["series"][0]["id"] == "A"
    with pytest.raises(ValueError):
        normalize_detection({"axes": {"x": {"ticks": []}, "y": {}}}, 1.0)


# ---------- 颜色提取 ----------

def test_extract_markers_by_color():
    import numpy as np
    rgb = np.array(Image.open(io.BytesIO(_synthetic_png())).convert("RGB"))
    pts, warnings = extract_points(rgb, "#d62728", PLOT_AREA)
    assert len(pts) == len(MARKERS)
    for (u, v), (x, y) in zip(pts, MARKERS):
        assert u == pytest.approx(_u(x), abs=1) and v == pytest.approx(_v(y), abs=1)


def test_extract_curve_by_color():
    import numpy as np
    rgb = np.array(Image.open(io.BytesIO(_synthetic_png())).convert("RGB"))
    pts, _ = extract_points(rgb, "#1f77b4", PLOT_AREA)
    assert len(pts) >= 10
    for p in pts:
        x, y = to_data(CAL, p)
        assert y == pytest.approx(0.03 * x + 0.5, abs=0.01)


def test_extract_marker_split_by_line_is_merged():
    import numpy as np
    img = Image.open(io.BytesIO(_synthetic_png()))
    d = ImageDraw.Draw(img)
    d.line([(_u(6), _v(0.6) - 20), (_u(6), _v(0.6) + 20)], fill=BLUE, width=2)  # 竖线切开 x=6 的红点
    pts, _ = extract_points(np.array(img.convert("RGB")), "#d62728", PLOT_AREA)
    assert len(pts) == len(MARKERS)
    assert pts[2] == pytest.approx([_u(6), _v(0.6)], abs=1)


def test_extract_missing_color_returns_empty_with_warning():
    import numpy as np
    rgb = np.array(Image.open(io.BytesIO(_synthetic_png())).convert("RGB"))
    pts, warnings = extract_points(rgb, "#2ca02c", PLOT_AREA)
    assert pts == [] and warnings


# ---------- 接口 ----------

@pytest.fixture(params=["json", "sqlite"])
def client(request, tmp_path, monkeypatch):
    monkeypatch.setattr("app.cache.DEMO_CACHE_DIR", tmp_path / "demo_cache")
    store = Store(tmp_path / "data") if request.param == "json" else SqlStore(tmp_path / "db.sqlite3")
    return TestClient(create_app(store)), store


def _upload(c, data=None, **form):
    return c.post("/api/m2/figures", data=form,
                  files={"image": ("fig.png", io.BytesIO(data or _synthetic_png()), "image/png")})


def _fake_vlm(monkeypatch, calls):
    monkeypatch.setattr(settings, "glm_base_url", "https://api.example.com")
    monkeypatch.setattr(settings, "glm_api_key", "test-key")

    async def fake_detect(data):
        calls.append(1)
        det = normalize_detection(DETECTION, 1.0)
        det["engine"] = {"vlm": "fake", "cached": False}
        return det
    monkeypatch.setattr("app.routers.m2.detect_figure", fake_detect)


def test_upload_and_get_image(client):
    c, _ = client
    r = _upload(c, doi="10.1/x", figure="图1(b)")
    assert r.status_code == 201
    fig = r.json()
    assert (fig["width"], fig["height"]) == (600, 400)
    assert fig["meta"] == {"doi": "10.1/x", "figure": "图1(b)"}
    img = c.get(fig["image_url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert img.content == _synthetic_png()
    assert c.get("/api/m2/figures/fig_nope/image").status_code == 404
    assert _upload(c, data=b"not an image").status_code == 400


def test_detect_503_without_vlm(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(settings, "glm_base_url", "")
    fig = _upload(c).json()
    r = c.post(f"/api/m2/figures/{fig['id']}/detect")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "VLM_UNAVAILABLE"


def test_detect_503_when_vlm_fails(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(settings, "glm_base_url", "https://api.example.com")
    monkeypatch.setattr(settings, "glm_api_key", "test-key")

    async def broken(data):
        raise ValueError("识别结果缺少 axes")
    monkeypatch.setattr("app.routers.m2.detect_figure", broken)
    fig = _upload(c).json()
    assert c.post(f"/api/m2/figures/{fig['id']}/detect").status_code == 503


def test_detect_then_cache_hit_by_sha256(client, monkeypatch):
    c, _ = client
    calls = []
    _fake_vlm(monkeypatch, calls)
    f1 = _upload(c).json()
    d1 = c.post(f"/api/m2/figures/{f1['id']}/detect").json()
    assert d1["figure_id"] == f1["id"] and d1["engine"]["cached"] is False
    assert d1["calibration"]["x"]["p2"]["value"] == 10

    # 同一张图重新上传：按 sha256 命中缓存，无 VLM 也能识别
    monkeypatch.setattr(settings, "glm_base_url", "")
    f2 = _upload(c).json()
    d2 = c.post(f"/api/m2/figures/{f2['id']}/detect").json()
    assert d2["figure_id"] == f2["id"] and d2["engine"]["cached"] is True
    assert len(calls) == 1


def test_extract_auto_writes_literature_dataset(client, monkeypatch):
    c, store = client
    _fake_vlm(monkeypatch, [])
    fig = _upload(c, doi="10.1/x", figure="图1(b)").json()
    c.post(f"/api/m2/figures/{fig['id']}/detect")
    body = {"schema_version": "0.6.0", "calibration": CAL, "mode": "auto", "series_id": "A",
            "columns": {"x": {"name": "氨氮浓度", "unit": "mg/L"}}}
    r = c.post(f"/api/m2/figures/{fig['id']}/extract", json=body)
    assert r.status_code == 200
    res = r.json()
    ds = res["dataset"]
    assert ds["source"] == "literature" and ds["meta"]["doi"] == "10.1/x"
    assert ds["meta"]["image_ref"] == fig["image_url"]
    assert ds["columns"] == [{"key": "x", "name": "氨氮浓度", "unit": "mg/L"},
                             {"key": "y", "name": "A", "unit": ""}]
    got = [(row["values"]["x"], row["values"]["y"]) for row in ds["rows"]]
    assert got == [pytest.approx(m, abs=0.03) for m in MARKERS]
    assert [p["point_id"] for p in res["points_px"]] == ["L1", "L2", "L3", "L4"]
    assert res["residual_px"] == pytest.approx(0.0)
    assert res["warnings"] == []
    assert store.get_dataset(ds["id"]) == ds

    # 同图同曲线再提取（手动修正）覆盖同一 dataset_id
    r2 = c.post(f"/api/m2/figures/{fig['id']}/extract",
                json={"calibration": CAL, "mode": "manual", "series_id": "A",
                      "points_px": [[180, 290], [260, 230]]})
    ds2 = r2.json()["dataset"]
    assert ds2["id"] == ds["id"]
    assert [r["values"] for r in ds2["rows"]] == [{"x": 2.0, "y": 0.2}, {"x": 4.0, "y": 0.4}]
    assert store.get_dataset(ds["id"])["rows"] == ds2["rows"]


def test_extract_auto_no_points_returns_empty_rows(client, monkeypatch):
    c, _ = client
    _fake_vlm(monkeypatch, [])
    fig = _upload(c, doi="10.1/x").json()
    c.post(f"/api/m2/figures/{fig['id']}/detect")
    r = c.post(f"/api/m2/figures/{fig['id']}/extract",
               json={"calibration": CAL, "mode": "auto", "series_id": "C"})
    assert r.status_code == 200
    assert r.json()["dataset"]["rows"] == [] and r.json()["warnings"]


def test_extract_manual_without_detection(client):
    c, _ = client
    fig = _upload(c).json()
    log_cal = {"x": {"scale": "log10", "p1": {"px": [100, 350], "value": 1},
                     "p2": {"px": [500, 350], "value": 10000}},
               "y": CAL["y"]}
    r = c.post(f"/api/m2/figures/{fig['id']}/extract",
               json={"calibration": log_cal, "mode": "manual", "points_px": [[200, 350], [300, 50]]})
    assert r.status_code == 200
    res = r.json()
    assert [row["values"] for row in res["dataset"]["rows"]] == [{"x": 10.0, "y": 0.0},
                                                                 {"x": 100.0, "y": 1.0}]
    assert res["residual_px"] is None
    assert res["dataset"]["columns"][0] == {"key": "x", "name": "x", "unit": ""}
    assert any("DOI" in w for w in res["warnings"])


def test_extract_errors(client):
    c, _ = client
    fig = _upload(c).json()
    url = f"/api/m2/figures/{fig['id']}/extract"
    bad = {"x": dict(CAL["x"], p2={"px": [100, 350], "value": 10}), "y": CAL["y"]}
    r = c.post(url, json={"calibration": bad, "mode": "manual", "points_px": [[1, 1]]})
    assert r.status_code == 422
    neg = {"x": dict(CAL["x"], scale="log10"), "y": CAL["y"]}
    assert c.post(url, json={"calibration": neg, "mode": "manual",
                             "points_px": [[1, 1]]}).status_code == 422
    assert c.post(url, json={"calibration": CAL, "mode": "manual"}).status_code == 400
    assert c.post(url, json={"calibration": CAL, "mode": "auto"}).status_code == 400
    assert c.post(url, json={"schema_version": "1.0.0", "calibration": CAL, "mode": "manual",
                             "points_px": []}).status_code == 409
    assert c.post("/api/m2/figures/fig_nope/extract",
                  json={"calibration": CAL, "mode": "manual", "points_px": []}).status_code == 404
