"""GEN-06～10 各步骤的意象锚点物件，全部透明背景、暗场反射（放在浅色页面上黑白分明）。

用法：... -- out.png w h samples <物件名>
  polymer  S1 高分子链球棍模型   建模：把实验抽象成结构 + 公式
  caliper  S2 游标卡尺           读数：把刻度变成数字
  prism    S3 三棱镜分光         分离：把曲线从图里剥离出来
  armilla  S4 浑天仪             规律：从观测数据推出定律
  nib      S5 钢笔尖与钴蓝墨滴   成文：落成一段能交的文字
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector
import lib

out, w, h, samples = lib.args()
which = sys.argv[sys.argv.index("--") + 5]
lib.reset()
lib.setup_render(w, h, samples, transparent=True)
lib.studio("night")

SILVER = lib.mat_silver(0.04)
BRUSHED = lib.mat_silver(0.22)
COBALT_GLASS = lib.mat_cobalt_glass(3.0)
INK = lib.principled("ink", **{"Base Color": (0.001, 0.0012, 0.002, 1), "Roughness": 0.6})
COBALT_GLOSS = lib.principled("cobalt_gloss", **{"Base Color": (0.015, 0.05, 1.0, 1), "Roughness": 0.08,
                                                 "Coat Weight": 1.0, "Coat Roughness": 0.03})


def sphere(loc, r, mat, seg=64):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=r, location=loc)
    o = bpy.context.active_object
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return o


def rod(a, b, r, mat, verts=32):
    a, b = Vector(a), Vector(b)
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, vertices=verts, location=(a + b) / 2)
    o = bpy.context.active_object
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return o


def box(size, loc, mat, rot=(0, 0, 0), bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale = size
    o.data.materials.append(mat)
    if bevel:
        m = o.modifiers.new("bev", "BEVEL")
        m.width = bevel
        m.segments = 3
    return o


def ring(r, t, loc=(0, 0, 0), rot=(0, 0, 0), mat=SILVER, flat=1.0):
    bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=t, major_segments=192, minor_segments=24,
                                     location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale.z = flat
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return o


if which == "polymer":
    # 螺旋主链：铬银碳原子 + 钴蓝玻璃侧基，银色键
    rnd = random.Random(3)
    n, R, pitch = 20, 0.55, 0.36
    pts = []
    for i in range(n):
        a = i * 2 * math.pi / 6.2
        pts.append(Vector((R * math.cos(a), R * math.sin(a), i * pitch / 1.0 - n * pitch / 2)))
    for i, p in enumerate(pts):
        sphere(p, 0.17, SILVER)
        if i:
            rod(pts[i - 1], p, 0.045, SILVER)
        if i % 2 == 0:
            out_dir = Vector((p.x, p.y, 0)).normalized()
            q = p + out_dir * 0.55 + Vector((0, 0, rnd.uniform(-0.1, 0.1)))
            rod(p, q, 0.035, SILVER)
            sphere(q, 0.13 if i % 4 else 0.19, COBALT_GLOSS)
    rig = bpy.data.objects.new("rig", None)
    bpy.context.collection.objects.link(rig)
    for o in list(bpy.context.scene.objects):
        if o.type == "MESH":
            o.parent = rig
    rig.rotation_euler = (math.radians(18), math.radians(52), math.radians(-20))
    lib.camera((0, -14, 0), (0, 0, 0), lens=60)

elif which == "caliper":
    # 主尺 + 固定量爪 + 游标滑块，刻度用细长墨色块
    box((7.0, 0.62, 0.07), (0, 0, 0), BRUSHED, bevel=0.01)
    box((0.5, 1.7, 0.07), (-3.25, -1.1, 0), BRUSHED, bevel=0.01)               # 固定量爪，与主尺相连
    box((1.5, 0.95, 0.12), (-1.1, -0.05, 0.05), SILVER, bevel=0.02)           # 游标滑块
    box((0.5, 1.7, 0.07), (-1.6, -1.1, 0.03), SILVER, bevel=0.01)              # 活动量爪，与滑块相连
    box((0.22, 0.3, 0.1), (-0.6, 0.55, 0.1), SILVER, bevel=0.02)               # 拇指轮
    for i in range(0, 66):
        x = -3.0 + i * 0.1
        if x < -1.85 or x > -0.35:
            tall = 0.24 if i % 10 == 0 else (0.17 if i % 5 == 0 else 0.11)
            box((0.018, tall, 0.006), (x, 0.31 - tall / 2, 0.037), INK)
    for i in range(11):                                                       # 游标刻度
        x = -1.75 + i * 0.09
        box((0.016, 0.12 if i % 5 else 0.18, 0.006), (x, -0.4, 0.112), INK)
    rig = bpy.data.objects.new("rig", None)
    bpy.context.collection.objects.link(rig)
    for o in list(bpy.context.scene.objects):
        if o.type == "MESH":
            o.parent = rig
    rig.rotation_euler = (math.radians(58), math.radians(0), math.radians(-24))
    lib.camera((0, -12, 1.2), (0.2, 0, -0.2), lens=58)

elif which == "prism":
    # 等边三棱镜；一束白光射入，另一侧散开成一束由白到钴蓝的扇形光
    bpy.ops.mesh.primitive_cylinder_add(vertices=3, radius=1.15, depth=2.2, location=(0, 0, 0))
    pr = bpy.context.active_object
    pr.rotation_euler = (math.pi / 2, -math.pi / 2, math.radians(14))  # 三角面朝相机，顶点朝上
    pr.data.materials.append(lib.mat_glass(ior=1.52))
    m = pr.modifiers.new("bev", "BEVEL")
    m.width, m.segments = 0.03, 4
    white = lib.mat_emit((1, 1, 1), 18)
    rod((-3.2, 0, -0.75), (-0.5, 0, 0.29), 0.028, white, 16)
    cols = [(1, 1, 1), (0.75, 0.82, 1), (0.45, 0.58, 1), (0.2, 0.35, 1), (0.06, 0.18, 1), (0.02, 0.08, 0.8)]
    for k, c in enumerate(cols):
        ang = math.radians(-8 - k * 4.5)
        start = Vector((0.5, 0, 0.27 - k * 0.03))
        end = start + Vector((math.cos(ang), 0, math.sin(ang))) * 3.2
        rod(start, end, 0.02, lib.mat_emit(c, 10 + k * 2), 12)
    lib.camera((0.3, -11, 0.6), (0.4, 0, -0.1), lens=50)

elif which == "armilla":
    # 浑天仪：赤道环、子午环、倾斜 23.4° 的黄道带，中心钴蓝玻璃球，贯穿地轴，底座
    ring(1.6, 0.035)
    ring(1.6, 0.035, rot=(math.pi / 2, 0, 0))
    ring(1.6, 0.035, rot=(math.pi / 2, 0, math.pi / 2))
    band = ring(1.45, 0.11, rot=(math.radians(23.4), 0, 0), mat=BRUSHED, flat=0.25)
    for i in range(72):
        a = i * 2 * math.pi / 72
        p = Vector((1.45 * math.cos(a), 1.45 * math.sin(a), 0))
        p.rotate(band.rotation_euler)
        rod(p * 0.96, p * (1.0 if i % 6 else 1.035), 0.006, INK, 6)
    ring(1.2, 0.022, rot=(math.radians(66.6), math.radians(30), 0))
    ring(0.95, 0.018, rot=(math.radians(-40), math.radians(60), 0))
    sphere((0, 0, 0), 0.38, COBALT_GLASS, 96)
    rod((0, 0.55, -1.95), (0, -0.55, 1.95), 0.03, SILVER)
    sphere((0, -0.55, 1.95), 0.07, SILVER)
    rod((0, 0, -1.65), (0, 0, -2.5), 0.08, BRUSHED)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.9, depth=0.12, vertices=128, location=(0, 0, -2.56))
    bpy.context.active_object.data.materials.append(SILVER)
    bpy.ops.object.shade_smooth()
    lib.camera((2.2, -9.5, 2.2), (0, 0, -0.25), lens=55)

elif which == "nib":
    # 钢笔尖：锥面的一部分，向笔尖收窄；导气孔 + 笔缝用布尔挖出；笔尖挂一滴钴蓝墨水
    L, U, V = 3.0, 90, 48
    verts, faces = [], []
    for i in range(U + 1):
        x = i / U * L
        r = 0.95  # 截面是一段平缓的弧
        hw = 0.52 * min(1.0, x / 1.7) ** 0.75 + 0.004  # 半宽：从笔尖张开到肩部，之后平行
        th = math.asin(min(hw / r, 0.99))
        for j in range(V + 1):
            ph = -th + 2 * th * j / V
            verts.append((x, r * math.sin(ph), r * math.cos(ph) - r))
    for i in range(U):
        for j in range(V):
            a = i * (V + 1) + j
            faces.append((a, a + 1, a + V + 2, a + V + 1))
    nib = lib.mesh_obj("nib", verts, faces, SILVER)
    lib.solidify(nib, 0.035, -1)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.075, depth=2, vertices=48, location=(1.35, 0, 0))
    hole = bpy.context.active_object
    slit = box((1.3, 0.012, 2), (0.66, 0, 0), INK)
    for cutter in (hole, slit):
        b = nib.modifiers.new("cut", "BOOLEAN")
        b.operation, b.object = "DIFFERENCE", cutter
        cutter.hide_render = True
    # 薄壳上 EXACT 求解器会得到空网格；依次尝试，取第一个有结果的
    dg = bpy.context.evaluated_depsgraph_get()
    for solver in ("MANIFOLD", "FLOAT", "EXACT"):
        for b in nib.modifiers:
            if b.type == "BOOLEAN":
                b.solver = solver
        dg.update()
        if len(nib.evaluated_get(dg).data.vertices):
            break
    ink = lib.principled("ink_drop", **{"Base Color": (0.01, 0.03, 0.55, 1), "Roughness": 0.03,
                                       "Coat Weight": 1.0, "Coat Roughness": 0.02})
    mb = bpy.data.metaballs.new("drop")
    mb.render_resolution = 0.006
    TIP = Vector((-1.0, 0, -0.6))
    for (dz, r) in [(-0.02, 0.1), (-0.13, 0.15), (-0.3, 0.22)]:  # 墨滴挂在笔尖下方（世界坐标，受重力向下）
        e = mb.elements.new()
        e.co, e.radius = TIP + Vector((0, -0.05, dz)), r
    drop = bpy.data.objects.new("drop", mb)
    bpy.context.collection.objects.link(drop)
    mb.materials.append(ink)
    rig = bpy.data.objects.new("rig", None)
    bpy.context.collection.objects.link(rig)
    nib.parent = rig
    hole.parent = rig
    slit.parent = rig
    # X 90° 让笔尖正面朝相机；Y −40° 让笔尖指向左下；再略微侧转出透视
    rig.rotation_euler = (math.radians(98), math.radians(-40), math.radians(-8))
    rig.location = TIP
    lib.camera((0, -8.5, 0.4), (0, 0, 0), lens=58)

lib.save(out)
