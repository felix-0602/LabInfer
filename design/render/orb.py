"""GEN-03 取数空状态：玻璃球放大镜。

一颗淡钴蓝的玻璃球，球心悬着十字准星和一段刻度尺（被「放大」的坐标轴），
底部托着一圈铬环。放在白色卡片上，透明背景。
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import lib

out, w, h, samples = lib.args()
lib.reset()
lib.setup_render(w, h, samples, transparent=True)
lib.studio("night", 1.0)

# 玻璃球：清玻璃表面 + 很淡的钴蓝体积吸收，边缘厚处更蓝
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=1.0)
orb = bpy.context.active_object
orb.data.materials.append(lib.mat_cobalt_glass(1.6))
bpy.ops.object.shade_smooth()

ink = lib.principled("ink", **{"Base Color": (0.004, 0.005, 0.008, 1), "Roughness": 0.4})
cobalt = lib.mat_emit((0.35, 0.45, 1.0), 14.0)
white = lib.mat_emit((1, 1, 1), 3.0)


def bar(size, loc, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale = size
    o.data.materials.append(mat)
    return o


# 球心十字准星（发光钴蓝细线）
bar((0.9, 0.012, 0.012), (0, 0, 0.05), cobalt)
bar((0.012, 0.012, 0.9), (0, 0, 0.05), cobalt)
bpy.ops.mesh.primitive_torus_add(major_radius=0.16, minor_radius=0.006, location=(0, 0, 0.05),
                                 rotation=(math.pi / 2, 0, 0))
bpy.context.active_object.data.materials.append(cobalt)

# 被放大的坐标轴：一根墨色轴线加刻度
bar((1.25, 0.03, 0.025), (0, 0.15, -0.38), ink)
for i in range(-6, 7):
    tall = 0.13 if i % 5 == 0 else 0.07
    bar((0.014, 0.02, tall), (i * 0.1, 0.15, -0.38 + tall / 2), ink)
# 一个被吸附的校准点
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.035, location=(0.0, 0.1, -0.38))
bpy.context.active_object.data.materials.append(white)

# 底部铬环与支架
silver = lib.mat_silver(0.06)
bpy.ops.mesh.primitive_torus_add(major_radius=0.82, minor_radius=0.035, major_segments=160,
                                 location=(0, 0, -0.62))
ring = bpy.context.active_object
ring.data.materials.append(silver)
bpy.ops.object.shade_smooth()
for k in range(3):
    a = k * 2 * math.pi / 3 + 0.4
    bar((0.03, 0.03, 0.34), (0.82 * math.cos(a), 0.82 * math.sin(a), -0.79), silver)
bpy.ops.mesh.primitive_cylinder_add(radius=0.95, depth=0.05, vertices=160, location=(0, 0, -0.97))
bpy.context.active_object.data.materials.append(silver)
bpy.ops.object.shade_smooth()

lib.camera((0, -6.2, 1.3), (0, 0, -0.12), lens=75)
lib.save(out)
