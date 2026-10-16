"""GEN-01 封面主视觉：银镜试管。

玻璃外壳里，内壁镀着一层上沿不规则的银镜，上沿之上散落着成核的银斑；
液态银从管口溢出，沿外壁往下淌，周围悬浮几滴银珠。透明背景。
"""
import math
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import lib

out, w, h, samples = lib.args()
lib.reset()
lib.setup_render(w, h, samples, transparent=True)
lib.studio("night")
bpy.context.scene.view_settings.exposure = 0.6  # 银镜要亮，整体提半档多

R, TOP = 0.62, 5.0
rig = bpy.data.objects.new("rig", None)
bpy.context.collection.objects.link(rig)


def profile(r, top, seg=28):
    pts = [(max(math.sin(a) * r, 1e-4), -math.cos(a) * r)
           for a in (i / seg * math.pi / 2 for i in range(seg + 1))]
    pts.append((r, top))
    return pts


def parent(o):
    o.parent = rig
    return o


# 玻璃外壳与管口翻边
glass = lib.mat_glass(tint=(0.97, 0.98, 1.0))
tube = parent(lib.lathe("tube", profile(R, TOP), 192, glass))
lib.solidify(tube, 0.035)
bpy.ops.mesh.primitive_torus_add(major_radius=R - 0.005, minor_radius=0.045,
                                 major_segments=192, minor_segments=24, location=(0, 0, TOP))
lip = parent(bpy.context.active_object)
lip.data.materials.append(glass)
bpy.ops.object.shade_smooth()

# 银镜层：上沿按角度起伏
silver = lib.mat_silver(0.03)
COAT = 2.6
wave = lambda a: 0.34 * math.sin(3 * a + 0.7) + 0.15 * math.sin(7 * a + 2.1) + 0.05 * math.sin(17 * a)
coat = parent(lib.lathe("coat", profile(R - 0.037, COAT, 40), 256, silver, top_offset=wave))
lib.solidify(coat, 0.004)

# 成核银斑：越往上越稀、越小
rnd = random.Random(11)
for i in range(110):
    a = rnd.uniform(0, 2 * math.pi)
    rise = rnd.random() ** 1.8 * 1.5
    z = COAT + wave(a) + 0.08 + rise
    s = (0.015 + rnd.random() * 0.05) * (1 - rise / 1.7)
    rr = R - 0.037 - 0.004
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=1,
                                         location=(rr * math.cos(a), rr * math.sin(a), z))
    d = parent(bpy.context.active_object)
    d.scale = (s * 0.35, s, s * 1.3)
    d.rotation_euler = (0, 0, a)
    d.data.materials.append(silver)
    bpy.ops.object.shade_smooth()

# 液态银：从管口溢出，沿外壁往下淌
liquid = lib.mat_silver(0.015)
mb = bpy.data.metaballs.new("liquid")
mb.resolution = 0.02
mb.render_resolution = 0.008
mb.threshold = 0.6
# 关键点之间插值出密集的小球，连成一股顺滑的液流，末端鼓成一滴将落未落的银珠
keys = [
    (0.0, -0.05, TOP + 0.06, 0.50), (0.32, -0.30, TOP + 0.10, 0.42), (0.62, -0.38, TOP - 0.05, 0.34),
    (0.72, -0.40, TOP - 0.40, 0.27), (0.73, -0.42, TOP - 0.85, 0.23), (0.73, -0.43, TOP - 1.25, 0.22),
    (0.73, -0.44, TOP - 1.50, 0.30),
]
for (x0, y0, z0, r0), (x1, y1, z1, r1) in zip(keys, keys[1:]):
    for t in [i / 8 for i in range(8)]:
        e = mb.elements.new()
        e.co = (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z0 + (z1 - z0) * t)
        e.radius = r0 + (r1 - r0) * t
        e.stiffness = 2.2
e = mb.elements.new()
e.co, e.radius = keys[-1][:3], keys[-1][3]
# 管口一圈薄薄的溢出银液
for i in range(24):
    a = -1.2 + i / 23 * 1.6
    e = mb.elements.new()
    e.co = ((R + 0.02) * math.cos(a), (R + 0.02) * math.sin(a), TOP + 0.02)
    e.radius = 0.16
    e.stiffness = 2.4
liq = parent(bpy.data.objects.new("liquid", mb))
bpy.context.collection.objects.link(liq)
mb.materials.append(liquid)

# 悬浮银珠
for x, y, z, r in [(1.55, -0.6, 3.9, 0.12), (1.9, -0.3, 2.7, 0.065), (1.2, -0.9, 1.4, 0.045),
                   (-1.35, -0.4, 4.6, 0.055), (2.25, 0.2, 4.9, 0.035), (-1.0, -0.8, 0.6, 0.03)]:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=r, location=(x, y, z))
    d = parent(bpy.context.active_object)
    d.scale.z = 1.12
    d.data.materials.append(liquid)
    bpy.ops.object.shade_smooth()

rig.location = (0, 0, -2.0)
rig.rotation_euler = (math.radians(4), math.radians(-14), math.radians(-25))

lib.camera((0, -17, 0.8), (0, 0, 0.45), lens=72)
lib.save(out)
