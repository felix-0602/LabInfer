"""M2 按颜色提取曲线像素点（OpenCV，延迟导入：未安装时不影响其他模块启动）。只给像素位置，不做数值换算。

策略：在绘图区内按目标颜色（Lab 空间距离）做掩膜，取连通域。
- 连通域都小（散点标记）：每个连通域的质心是一个点。
- 有大连通域（连续曲线）：沿 u 方向等距取列，每列取掩膜像素 v 的中位数。
分离失败时返回空点列和警告，由 M8 转手动点取。
"""

import numpy as np

_COLOR_TOL = 28.0        # Lab 空间欧氏距离阈值
_MARKER_MAX_FRAC = 0.04  # 连通域外接框长边不超过绘图区宽的这一比例，视为散点标记
_CURVE_SAMPLES = 20      # 连续曲线的采样列数
_MIN_AREA = 4            # 小于该像素数的连通域视为噪点
_INSET = 3               # 绘图区向内收缩，避开坐标轴边框
_MERGE_GAP = 3           # 标记碎块外接框间距不超过该像素数时合并


def parse_hex(color: str) -> tuple[int, int, int]:
    """'#1f77b4' → (r, g, b)。格式不对抛 ValueError。"""
    s = (color or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        raise ValueError(f"颜色格式应为 #rrggbb: {color!r}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _lab(rgb_img: np.ndarray) -> np.ndarray:
    import cv2
    return cv2.cvtColor(rgb_img.astype(np.float32) / 255.0, cv2.COLOR_RGB2Lab)


def decode_rgb(data: bytes) -> np.ndarray:
    import cv2
    arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise ValueError("无法解码图片")
    return cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)


def _merge_fragments(comps, stats, centroids, u0: int, v0: int) -> list[list[float]]:
    """同一个标记被其他曲线穿过会断成几块：外接框相交或相距很近的连通域按面积加权合并成一个点。"""
    import cv2
    boxes = []
    for i in comps:
        x, y = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP]
        boxes.append([x, y, x + stats[i, cv2.CC_STAT_WIDTH], y + stats[i, cv2.CC_STAT_HEIGHT],
                      float(stats[i, cv2.CC_STAT_AREA]),
                      float(centroids[i][0]), float(centroids[i][1])])
    merged = True
    while merged:
        merged = False
        for a in range(len(boxes)):
            for b in range(a + 1, len(boxes)):
                A, B = boxes[a], boxes[b]
                g = _MERGE_GAP
                if A[0] <= B[2] + g and B[0] <= A[2] + g and A[1] <= B[3] + g and B[1] <= A[3] + g:
                    area = A[4] + B[4]
                    boxes[a] = [min(A[0], B[0]), min(A[1], B[1]), max(A[2], B[2]), max(A[3], B[3]),
                                area, (A[5] * A[4] + B[5] * B[4]) / area,
                                (A[6] * A[4] + B[6] * B[4]) / area]
                    del boxes[b]
                    merged = True
                    break
            if merged:
                break
    return [[b[5] + u0, b[6] + v0] for b in boxes]


def extract_points(rgb: np.ndarray, color: str, plot_area: dict | None = None,
                   tol: float = _COLOR_TOL) -> tuple[list[list[float]], list[str]]:
    """返回 (按 u 升序的像素点 [[u, v], …], warnings)。"""
    import cv2
    h, w = rgb.shape[:2]
    try:
        target = parse_hex(color)
    except ValueError as e:
        return [], [str(e)]

    if plot_area:
        u0 = max(0, int(plot_area.get("u0", 0)) + _INSET)
        v0 = max(0, int(plot_area.get("v0", 0)) + _INSET)
        u1 = min(w, int(plot_area.get("u1", w)) - _INSET + 1)
        v1 = min(h, int(plot_area.get("v1", h)) - _INSET + 1)
    else:
        u0, v0, u1, v1 = 0, 0, w, h
    if u1 - u0 < 2 or v1 - v0 < 2:
        return [], ["绘图区过小或越界，无法提取"]

    roi = rgb[v0:v1, u0:u1]
    target_lab = _lab(np.array([[target]], dtype=np.uint8))[0, 0]
    dist = np.linalg.norm(_lab(roi) - target_lab, axis=2)
    mask = (dist <= tol).astype(np.uint8)

    n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    comps = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= _MIN_AREA]
    if not comps:
        return [], [f"绘图区内未找到颜色 {color} 的像素，可能颜色相近或曲线被遮挡，请改用手动点取"]

    max_side = max(8, int((u1 - u0) * _MARKER_MAX_FRAC))
    big = [i for i in comps
           if max(stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]) > max_side]
    warnings: list[str] = []
    if not big:
        pts = _merge_fragments(comps, stats, centroids, u0, v0)
    else:
        keep = np.isin(labels, comps)
        cols = np.where(keep.any(axis=0))[0]
        picks = np.unique(np.linspace(cols[0], cols[-1], _CURVE_SAMPLES).round().astype(int))
        pts = []
        for c in picks:
            vs = np.where(keep[:, c])[0]
            if vs.size:
                pts.append([float(c) + u0, float(np.median(vs)) + v0])
        if len(big) < len(comps):
            warnings.append("同色像素中同时存在曲线和散点，结果按连续曲线采样，请检查")
    pts.sort(key=lambda p: p[0])
    return [[round(p[0], 1), round(p[1], 1)] for p in pts], warnings
