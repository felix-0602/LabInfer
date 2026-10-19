"""ART-02（原 PHOTO-02 位）：旧期刊印刷页微距，程序绘制，不是照片。

画面：一页双栏期刊斜放在镜头下，近处是一张滴定曲线插图（坐标轴、刻度、数据点、灰色变色带），
灰色区域用 45° 半调网点印出来，正文是看不清的字块；整页做透视倾斜和景深模糊，像微距拍到的印刷页。
页面再映射成「钴蓝 → 白」双色调并降低不透明度（design/styles.css .duo-day），只做情绪底纹，内容不可读。

用法：python3 journal.py ../assets/PHOTO-02.jpg
依赖：numpy、Pillow。
"""
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "PHOTO-02.jpg"
W, H = 1200, 1600
PW, PH = 2400, 3000  # 页面先画大，再透视压到成品尺寸
rng = np.random.default_rng(11)


def text_block(d, x0, y0, x1, y1, lh=34, size=15):
    """看不清的正文：按词长随机的字块，段末短行，偶尔空行分段。"""
    y = y0
    while y + size < y1:
        x = x0 + (40 if rng.random() < 0.12 else 0)
        end = x1 - (rng.integers(200, 600) if rng.random() < 0.12 else 0)
        while x < end:
            w = int(rng.integers(18, 90))
            if x + w > end:
                break
            d.rounded_rectangle([x, y, x + w, y + size], radius=3, fill=40)
            x += w + int(rng.integers(9, 14))
        y += lh + (lh if rng.random() < 0.06 else 0)


def figure(line, tint, x0, y0, w, h):
    """插图：pH–V 滴定曲线，两个突跃，灰带是指示剂变色区（半调层），坐标与数据点是实线层。"""
    ax0, ay0, ax1, ay1 = x0 + 110, y0 + 40, x0 + w - 30, y0 + h - 90
    tint.rectangle([ax0 + (ax1 - ax0) * 0.56, ay0, ax0 + (ax1 - ax0) * 0.66, ay1], fill=150)
    tint.rectangle([ax0, ay0 + (ay1 - ay0) * 0.62, ax1, ay0 + (ay1 - ay0) * 0.72], fill=205)
    line.rectangle([ax0, ay0, ax1, ay1], outline=20, width=4)
    for i in range(11):
        x = ax0 + (ax1 - ax0) * i / 10
        line.line([x, ay1, x, ay1 - (22 if i % 2 == 0 else 12)], fill=20, width=3)
        if i % 2 == 0:
            line.rounded_rectangle([x - 18, ay1 + 18, x + 18, ay1 + 38], radius=3, fill=40)
    for i in range(8):
        y = ay1 - (ay1 - ay0) * i / 7
        line.line([ax0, y, ax0 + 14, y], fill=20, width=3)
        line.rounded_rectangle([ax0 - 58, y - 10, ax0 - 22, y + 10], radius=3, fill=40)

    def ph(t):  # 两段 S 形突跃，形状像 Na₂CO₃ 被 HCl 滴定
        return 0.92 - 0.30 / (1 + math.exp(-(t - 0.30) * 30)) - 0.48 / (1 + math.exp(-(t - 0.61) * 40))

    pts = [(ax0 + (ax1 - ax0) * t, ay0 + (ay1 - ay0) * (1 - ph(t))) for t in np.linspace(0.02, 0.98, 400)]
    line.line(pts, fill=10, width=6, joint="curve")
    for t in np.linspace(0.05, 0.95, 19):
        x, y = ax0 + (ax1 - ax0) * t, ay0 + (ay1 - ay0) * (1 - ph(t) + rng.normal(0, 0.008))
        line.ellipse([x - 10, y - 10, x + 10, y + 10], outline=10, width=4, fill=255)
    line.rectangle([ax1 - 330, ay0 + 30, ax1 - 30, ay0 + 120], outline=20, width=3, fill=255)
    for k in range(2):
        line.line([ax1 - 310, ay0 + 58 + k * 36, ax1 - 250, ay0 + 58 + k * 36], fill=10, width=5)
        line.rounded_rectangle([ax1 - 230, ay0 + 50 + k * 36, ax1 - 70, ay0 + 66 + k * 36], radius=3, fill=40)
    # 图注
    text_block(line, x0 + 20, y0 + h - 30, x0 + w - 20, y0 + h + 60, lh=30, size=13)


def halftone(gray, cell=14, angle=45):
    """把灰度层印成网点：旋转网格，每格一个圆点，面积跟墨量成正比。"""
    h, w = gray.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angle)
    u = (xs * math.cos(a) + ys * math.sin(a)) / cell
    v = (-xs * math.sin(a) + ys * math.cos(a)) / cell
    du, dv = u - np.round(u), v - np.round(v)
    dist = np.sqrt(du ** 2 + dv ** 2)
    ink = 1 - gray / 255.0
    radius = np.sqrt(ink / math.pi) * 1.05
    return np.where(dist < radius, 30, 255).astype(np.uint8)


def main():
    line_img = Image.new("L", (PW, PH), 255)
    tint_img = Image.new("L", (PW, PH), 255)
    line, tint = ImageDraw.Draw(line_img), ImageDraw.Draw(tint_img)

    # 页眉线、栏间距、双栏正文，左栏中部是插图
    line.line([140, 150, PW - 140, 150], fill=30, width=3)
    line.rounded_rectangle([140, 100, 560, 124], radius=3, fill=60)
    line.rounded_rectangle([PW - 340, 100, PW - 140, 124], radius=3, fill=60)
    col = (PW - 280 - 80) // 2
    text_block(line, 140, 210, 140 + col, 900)
    figure(line, tint, 140, 960, col + 360, 1100)
    text_block(line, 140, 2260, 140 + col, PH - 120)
    text_block(line, 140 + col + 80, 210, PW - 140, 940)
    text_block(line, 140 + col + 440, 980, PW - 140, 2180)
    text_block(line, 140 + col + 80, 2260, PW - 140, PH - 120)
    # 右栏顶部一块灰色表格底纹，也走半调
    tint.rectangle([140 + col + 80, 960, 140 + col + 400, 2180], fill=230)

    page = np.minimum(np.asarray(line_img), halftone(np.asarray(tint_img).astype(np.float32)))
    # 油墨在纸上略微晕开 + 纸张纤维
    page = Image.fromarray(page).filter(ImageFilter.GaussianBlur(1.2))
    paper = np.asarray(page).astype(np.float32)
    fibers = rng.normal(0, 1, (PH // 4, PW // 4)).astype(np.float32)
    fibers = np.asarray(Image.fromarray(((fibers + 4) * 30).clip(0, 255).astype(np.uint8)).resize((PW, PH), Image.BICUBIC)).astype(np.float32)
    paper = np.clip(paper * 0.94 + (fibers - 120) * 0.06 + 6, 0, 255)
    page = Image.fromarray(paper.astype(np.uint8))

    # 透视：页面上端远、下端近，并向左旋一点，取插图附近一块做微距画面
    page = page.rotate(-8, resample=Image.BICUBIC, expand=False, fillcolor=235)
    src_quad = (300, 700, 60, 2700, 2300, 2900, 2050, 820)  # PIL QUAD 顺序：左上、左下、右下、右上
    shot = page.transform((W, H), Image.QUAD, src_quad, resample=Image.BICUBIC)

    # 景深：插图所在的中间一段清楚，上下渐虚
    blur = shot.filter(ImageFilter.GaussianBlur(9))
    yy = np.linspace(0, 1, H)[:, None]
    sharp = np.exp(-((yy - 0.48) / 0.20) ** 2)
    out = np.asarray(shot) * sharp + np.asarray(blur) * (1 - sharp)
    # 微距的暗角
    xx = np.linspace(-1, 1, W)[None, :]
    out *= 1 - 0.18 * (xx ** 2 + ((yy - 0.5) * 2) ** 2)
    out = np.clip(out + rng.normal(0, 3, out.shape), 0, 255).astype(np.uint8)
    Image.fromarray(out, "L").save(OUT, quality=88)
    print("saved", OUT)


if __name__ == "__main__":
    main()
