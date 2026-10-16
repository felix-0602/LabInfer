"""GEN-04 导出报告页眉横幅：银镜碎片迸射。

铬银、钴蓝玻璃、磨砂白玻璃三种碎片，从右侧中心向外迸射，景深虚化前后层。
左侧 40% 保持干净，方便叠标题。不透明背景（白到冷灰）。
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
lib.reset()
lib.setup_render(w, h, samples, transparent=False, look="AgX - Medium Contrast")
lib.studio("night", 1.0)

# 相机看到的背景是干净的白，反射里仍然是影棚（用 Light Path 区分相机光线）
nt = bpy.context.scene.world.node_tree
bg = nt.nodes["Background"]
studio_col = bg.inputs["Color"].links[0].from_socket
lp = nt.nodes.new("ShaderNodeLightPath")
mix = nt.nodes.new("ShaderNodeMixRGB")
mix.inputs["Color2"].default_value = (3.2, 3.24, 3.36, 1)  # 经 AgX 映射后约为纸白
nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
nt.links.new(studio_col, mix.inputs["Color1"])
nt.links.new(mix.outputs[0], bg.inputs["Color"])

mats = [lib.mat_silver(0.03), lib.mat_cobalt_glass(6.0), lib.mat_glass(rough=0.25)]
weights = [0.45, 0.35, 0.2]
rnd = random.Random(23)
O = Vector((3.6, 0, 0.1))  # 迸射中心，在画面右侧

for i in range(340):
    # 方向偏向左侧和上下两侧，少量向右
    a = rnd.gauss(math.pi, 0.95) if rnd.random() < 0.8 else rnd.uniform(0, 2 * math.pi)
    elev = rnd.gauss(0, 0.35)
    d = Vector((math.cos(a), rnd.uniform(-0.6, 0.6), math.sin(a) * 0.55 + elev)).normalized()
    dist = 0.25 + rnd.random() ** 1.6 * 6.5
    p = O + d * dist
    if p.x < -1.2 and rnd.random() < 0.85:
        continue  # 左侧留白
    length = 0.18 + dist * 0.16 * rnd.uniform(0.5, 1.7)
    width = length * rnd.uniform(0.15, 0.45)
    # 不规则三角 / 四边形碎片
    pts = [(0, length * 0.5), (width * rnd.uniform(0.3, 0.6), -length * rnd.uniform(0.2, 0.5)),
           (-width * rnd.uniform(0.3, 0.6), -length * 0.5)]
    if rnd.random() < 0.4:
        pts.insert(2, (width * rnd.uniform(-0.2, 0.2), -length * 0.55))
    verts = [(x, y, 0) for x, y in pts]
    o = lib.mesh_obj(f"shard{i}", verts, [tuple(range(len(verts)))],
                     rnd.choices(mats, weights)[0], smooth=False)
    lib.solidify(o, rnd.uniform(0.02, 0.06), 0)
    bev = o.modifiers.new("bev", "BEVEL")
    bev.width = 0.003
    o.location = p
    # 长轴沿迸射方向，再随机翻滚
    o.rotation_euler = d.to_track_quat("Y", "Z").to_euler()
    o.rotation_euler.rotate_axis("Y", rnd.uniform(0, math.pi))
    o.rotation_euler.rotate_axis("X", rnd.uniform(-0.6, 0.6))

cam = lib.camera((0.6, -11, 0.2), (0.6, 0, 0.1), lens=48, dof=(11.0, 1.1))
lib.save(out)
