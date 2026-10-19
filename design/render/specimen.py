"""ART-01（原 PHOTO-01 位）：滴定终点样片，程序渲染，不是照片。

画面：滴定管尖悬着一滴将落未落的液滴，下方一滴正在下落，最下面是锥形瓶里的液面和一圈涟漪。
用 numpy 做有向距离场光线步进，影棚是暗场 + 两条竖向长条灯 + 顶部柔光，只输出灰度，
页面再映射成「墨黑 → 钴蓝」双色调（design/styles.css .duo-night）。

用法：python3 specimen.py ../assets/PHOTO-01.jpg [宽 高]
依赖：numpy、Pillow。
"""
import sys

import numpy as np
from PIL import Image, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "PHOTO-01.jpg"
W, H = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1000, 1250)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def tip(p):
    """滴定管尖：上段直管，下段收成锥形尖嘴，略微倾斜。"""
    x, y, z = p[..., 0] - 0.02 * (y_ := p[..., 1]), y_, p[..., 2]
    r = np.where(y > 0.30, 0.10, 0.026 + (0.10 - 0.026) * np.clip((y - 0.06) / 0.24, 0, 1) ** 1.6)
    d_side = np.hypot(x, z) - r
    d_cap = 0.06 - y  # 尖嘴下端截平
    return np.maximum(d_side, d_cap)


def drops(p):
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    # 悬滴：略被重力拉长
    hang = np.sqrt(x ** 2 + ((y - 0.012) * 1.12) ** 2 + z ** 2) - 0.052
    # 落滴：上尖下圆
    fy = y + 0.30
    fall = np.sqrt(x ** 2 + (fy * np.where(fy > 0, 0.72, 1.0)) ** 2 + z ** 2) - 0.026
    return hang, fall


def surface(p):
    """锥形瓶液面：平面加一圈向外扩散的涟漪。"""
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    rr = np.hypot(x, z)
    ripple = 0.012 * np.sin(rr * 55 - 1.2) * np.exp(-rr * 3.2)
    return y + 0.62 - ripple


def scene(p):
    t = tip(p)
    hang, fall = drops(p)
    body = smin(t, hang, 0.035)
    d = np.minimum(np.minimum(body, fall), surface(p))
    mat = np.where(surface(p) <= d + 1e-5, 2, np.where(fall <= d + 1e-5, 1, 0))
    return d, mat


def env(dirs):
    """影棚：暗场，左右两条竖向长条灯，顶部柔光，地面微光。"""
    x, y, z = dirs[..., 0], dirs[..., 1], dirs[..., 2]
    az = np.arctan2(x, -z)
    strip = lambda c, w: np.exp(-((az - c) / w) ** 6)
    v = 0.01 + 0.02 * np.clip(y, 0, 1)
    v += 4.0 * strip(-0.95, 0.16) * np.clip(1.3 - abs(y) * 1.3, 0, 1)
    v += 2.6 * strip(0.85, 0.09) * np.clip(1.1 - abs(y - 0.1) * 1.4, 0, 1)
    # 顶部一块窄的矩形柔光箱：液面的涟漪靠它反出亮环
    v += 3.0 * (y > 0.72) * np.exp(-(x / 0.18) ** 4)
    v += 0.8 * strip(2.6, 0.3) * np.clip(0.6 - abs(y), 0, 1)  # 背后的反光板
    # 正前方远处一条低矮的横向灯带：液面把它反成一条被涟漪扭弯的亮线
    v += 1.5 * np.exp(-((y - 0.10) / 0.05) ** 2) * np.exp(-(az / 0.8) ** 4)
    return v


def normal(p):
    e = 1e-3
    n = np.stack([
        scene(p + np.array([e, 0, 0]))[0] - scene(p - np.array([e, 0, 0]))[0],
        scene(p + np.array([0, e, 0]))[0] - scene(p - np.array([0, e, 0]))[0],
        scene(p + np.array([0, 0, e]))[0] - scene(p - np.array([0, 0, e]))[0],
    ], -1)
    return n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9)


def render(W, H, y0, y1):
    """渲染第 y0–y1 行（分块渲染，控制内存）。"""
    aspect = W / H
    ys, xs = np.mgrid[y0:y1, 0:W].astype(np.float32)
    u = (xs + 0.5) / W * 2 - 1
    v = 1 - (ys + 0.5) / H * 2
    ro = np.array([0.0, 0.10, 2.6], np.float32)
    rd = np.stack([u * aspect * 0.31, v * 0.31 - 0.07, -np.ones_like(u)], -1)
    rd /= np.linalg.norm(rd, axis=-1, keepdims=True)

    t = np.zeros(u.shape, np.float32)
    hit = np.zeros(u.shape, bool)
    for _ in range(140):
        p = ro + rd * t[..., None]
        d, _m = scene(p)
        hit |= d < 4e-4
        t = np.where(hit, t, t + d * 0.9)
        if (t > 6).all():
            break
    hit &= t < 6
    p = ro + rd * t[..., None]
    _, mat = scene(p)
    n = normal(p)

    cosi = np.clip(-(rd * n).sum(-1), 0, 1)
    # 银镜质感：玻璃的反射底数取得很高（R2 铬银），液面保持接近真实水面
    fres = np.where(mat == 2, 0.06, 0.28) + np.where(mat == 2, 0.94, 0.72) * (1 - cosi) ** 5
    refl = rd - 2 * (rd * n).sum(-1, keepdims=True) * n
    refr = rd + 0.35 * n  # 近似的折射偏折，玻璃和液体都只取一个方向
    refr /= np.linalg.norm(refr, axis=-1, keepdims=True)

    glass = fres * env(refl) * 1.6 + 0.55 * env(refr) * (1 - fres)
    liquid = fres * env(refl) * 2.0 + 0.015
    col = np.where(mat == 2, liquid * 0.9, glass)
    # 边缘暗线：玻璃厚度在轮廓处变暗，形体更清楚
    col *= np.where(mat == 2, 1.0, 0.35 + 0.65 * cosi ** 0.4)

    bg = 0.03 + 0.05 * np.exp(-((u * 0.8) ** 2 + (v + 0.2) ** 2) * 1.5)
    img = np.where(hit, col, bg)
    img = img / (1 + img)  # 色调映射
    img = np.clip(img * 2.1, 0, 1) ** 0.9
    return img


def main():
    ss = 2  # 2×2 超采样，涟漪的细线不出锯齿
    BW, BH = W * ss, H * ss
    img = np.concatenate([render(BW, BH, y, min(y + 250, BH)) for y in range(0, BH, 250)])
    img = img.reshape(H, ss, W, ss).mean((1, 3))
    # 胶片颗粒 + 轻微柔焦，像一张真实拍下的近摄样片
    rng = np.random.default_rng(7)
    img = np.clip(img + rng.normal(0, 0.025, img.shape), 0, 1)
    im = Image.fromarray((img * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.6))
    im.save(OUT, quality=90)
    print("saved", OUT, im.size)


if __name__ == "__main__":
    main()
