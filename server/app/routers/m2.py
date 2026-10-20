import io
import json
import os
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from ..cache import cache_get, cache_put, sha256_bytes
from ..config import CONTRACT_VERSION
from ..llm import LlmError, llm_configured
from ..services.calibration import CalibrationError, residual_px, to_data, validate_calibration
from ..services.curve_extract import decode_rgb, extract_points
from ..services.figure_detect import assess_intent, detect_figure
from ..storage import new_id

router = APIRouter(prefix="/api/m2", tags=["m2"])

_FORMATS = {"PNG": (".png", "image/png"), "JPEG": (".jpg", "image/jpeg")}
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _error(status: int, code: str, message: str, detail: dict | None = None):
    return JSONResponse(status_code=status, content={
        "error": {"code": code, "message": message, "detail": detail or {}}})


def _not_found(id: str):
    return _error(404, "NOT_FOUND", f"figure 不存在: {id}")


# Figure 记录是 M2 内部状态（原图路径、识别结果），不进共享存储的契约对象，
# 两种存储后端都放在数据根目录的 figures/ 下。

def _figure_path(store, id: str) -> Path | None:
    if not _ID_RE.match(id):
        return None
    return Path(store.root) / "figures" / f"{id}.json"


def _load_figure(store, id: str) -> dict | None:
    p = _figure_path(store, id)
    if p is None or not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _save_figure(store, rec: dict) -> None:
    p = _figure_path(store, rec["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _figure_out(rec: dict) -> dict:
    return {"schema_version": CONTRACT_VERSION, "id": rec["id"],
            "image_url": f"/api/m2/figures/{rec['id']}/image",
            "width": rec["width"], "height": rec["height"], "sha256": rec["sha256"],
            "meta": rec["meta"]}


@router.post("/figures", status_code=201)
async def upload_figure(request: Request, image: UploadFile = File(...),
                        doi: str | None = Form(None), figure: str | None = Form(None)):
    from PIL import Image, UnidentifiedImageError
    data = await image.read()
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        width, height = img.size
    except (UnidentifiedImageError, OSError):
        fmt = None
    if fmt not in _FORMATS:
        return _error(400, "BAD_REQUEST", "image 必须是 PNG 或 JPG 图片")

    store = request.app.state.store
    suffix, media_type = _FORMATS[fmt]
    path = store.save_upload(data, suffix)
    rec = {"id": new_id("fig"), "path": str(path), "media_type": media_type,
           "width": width, "height": height, "sha256": sha256_bytes(data),
           "meta": {"doi": doi or None, "figure": figure or None}, "detection": None}
    _save_figure(store, rec)
    return _figure_out(rec)


@router.get("/figures/{id}/image")
def get_figure_image(id: str, request: Request):
    rec = _load_figure(request.app.state.store, id)
    if rec is None or not Path(rec["path"]).exists():
        return _not_found(id)
    return FileResponse(rec["path"], media_type=rec["media_type"])


@router.post("/figures/{id}/detect")
async def detect(id: str, request: Request, context_id: str | None = None):
    """识别坐标轴与图例。带 context_id 时附 intent（0.9.0）：图与该实验是否同类的确定性裁决。
    识别结果（含 chart 语义）按图哈希缓存；intent 依赖实验上下文，不进缓存、每次现算。"""
    store = request.app.state.store
    rec = _load_figure(store, id)
    if rec is None:
        return _not_found(id)
    ctx = store.get_context(context_id) if context_id else None

    cached = cache_get("m2", rec["sha256"])
    if cached is not None:
        det = cached
        det.setdefault("engine", {})["cached"] = True
    elif llm_configured():
        data = Path(rec["path"]).read_bytes()
        try:
            det = await detect_figure(data)
        except (LlmError, ValueError) as e:
            return _error(503, "VLM_UNAVAILABLE", f"图表识别失败: {e}")
        cache_put("m2", rec["sha256"], dict(det))
    else:
        return _error(503, "VLM_UNAVAILABLE", "视觉模型未配置且未命中演示缓存")

    if ctx is not None:
        intent = assess_intent(det.get("chart"), ctx)
        intent["chart"] = det.get("chart")
        det["intent"] = intent

    det["schema_version"] = CONTRACT_VERSION
    det["figure_id"] = id
    rec["detection"] = det
    _save_figure(store, rec)
    return det


def _major(version) -> str:
    return str(version).split(".")[0]


def _dataset_id(fig_id: str, series_id: str | None) -> str:
    key = re.sub(r"[^A-Za-z0-9_-]", "_", series_id or "manual")[:32]
    return f"ds_lit_{fig_id.removeprefix('fig_')}_{key}"


def _sig(v: float) -> float:
    return float(f"{v:.6g}")


@router.post("/figures/{id}/extract")
def extract(id: str, request: Request, body: dict):
    store = request.app.state.store
    # 单用户架构：按路径 id 取图，不做归属校验；改多用户前须补上，见 architecture.md「系统形态」
    rec = _load_figure(store, id)
    if rec is None:
        return _not_found(id)

    if not isinstance(body, dict):
        return _error(400, "BAD_REQUEST", "请求体必须是 ExtractRequest 对象")
    sv = body.get("schema_version", CONTRACT_VERSION)
    if _major(sv) != _major(CONTRACT_VERSION):
        return _error(409, "SCHEMA_VERSION_MISMATCH",
                      f"schema_version 主版本不一致: {sv} vs {CONTRACT_VERSION}")
    mode = body.get("mode", "auto")
    series_id = body.get("series_id")
    calibration = body.get("calibration")
    if mode not in ("auto", "manual"):
        return _error(400, "BAD_REQUEST", f"mode 只能是 auto 或 manual: {mode!r}")
    if not isinstance(calibration, dict):
        return _error(400, "BAD_REQUEST", "缺少 calibration")
    if mode == "auto" and not series_id:
        return _error(400, "BAD_REQUEST", "auto 模式需要 series_id")
    try:
        validate_calibration(calibration)
    except CalibrationError as e:
        return _error(422, "CALIBRATION_INVALID", str(e))

    det = rec.get("detection") or {}
    series = next((s for s in det.get("series") or [] if s.get("id") == series_id), None)
    warnings: list[str] = []

    if mode == "manual":
        raw = body.get("points_px")
        if not isinstance(raw, list):
            return _error(400, "BAD_REQUEST", "manual 模式需要 points_px: [[u, v], …]")
        try:
            pts = [[float(p[0]), float(p[1])] for p in raw]
        except (TypeError, ValueError, IndexError):
            return _error(400, "BAD_REQUEST", "points_px 每项必须是 [u, v] 数值对")
        if not pts:
            warnings.append("points_px 为空，数据集没有数据点")
    elif series is None:
        pts = []
        warnings.append(f"未识别到曲线 {series_id}（需先调用识别接口），请改用手动点取")
    elif not series.get("color"):
        pts = []
        warnings.append(f"曲线 {series_id} 没有识别到颜色，请改用手动点取")
    else:
        rgb = decode_rgb(Path(rec["path"]).read_bytes())
        pts, ws = extract_points(rgb, series["color"], det.get("plot_area"))
        warnings.extend(ws)

    rows, points_px = [], []
    try:
        for i, p in enumerate(pts, start=1):
            x, y = to_data(calibration, p)
            pid = f"L{i}"
            rows.append({"id": pid, "series": "std",
                         "values": {"x": _sig(x), "y": _sig(y)}, "verified": False})
            points_px.append({"point_id": pid, "px": [round(p[0], 1), round(p[1], 1)]})
    except (CalibrationError, OverflowError) as e:
        return _error(422, "CONVERSION_FAILED", f"无法换算: {e}")

    axes = det.get("axes") or {}
    cols_req = body.get("columns") or {}
    columns = []
    for axis in ("x", "y"):
        c = cols_req.get(axis) or {}
        a = axes.get(axis) or {}
        columns.append({"key": axis, "name": c.get("name") or a.get("label") or axis,
                        "unit": c.get("unit") if c.get("unit") is not None else a.get("unit", "")})

    meta = rec["meta"]
    if not meta.get("doi"):
        warnings.append("来源为空：DOI、链接或报告号/标准号（如 USGS TWRI 9-A6.6）任填一个，"
                        "文献数据集才算有出处；填过再重新提取即可")
    label = (series or {}).get("label") or series_id or "手动点取"
    title = " · ".join(t for t in (meta.get("figure"), label) if t)
    ds = {
        "schema_version": CONTRACT_VERSION,
        "id": _dataset_id(id, series_id),
        "source": "literature",
        "meta": {"title": title, "doi": meta.get("doi"), "figure": meta.get("figure"),
                 "image_ref": f"/api/m2/figures/{id}/image"},
        "columns": columns,
        "rows": rows,
    }
    store.put_dataset(ds)
    return {"schema_version": CONTRACT_VERSION, "dataset": ds, "points_px": points_px,
            "residual_px": residual_px(calibration, axes), "warnings": warnings}
