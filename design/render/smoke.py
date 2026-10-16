"""GEN-02 封面暗场烟雾 / GEN-05 浅色墨迹底。

一块铺满正交相机的平面，只有发光着色器：域扭曲噪声（用一层噪声去扭曲另一层的坐标）
得到烟雾 / 墨迹的流动形态，再用色带映射成钴蓝。
用法：... -- out.png 2880 1800 16 night|day
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import lib

out, w, h, samples = lib.args()
variant = (sys.argv[sys.argv.index("--") + 5] if len(sys.argv) > sys.argv.index("--") + 5 else "night")
lib.reset()
lib.setup_render(w, h, samples, transparent=False, look="None")
bpy.context.scene.view_settings.view_transform = "Standard"
lib.world((0, 0, 0), 0)

aspect = w / h
bpy.ops.mesh.primitive_plane_add(size=1)
plane = bpy.context.active_object
plane.scale = (aspect, 1, 1)
lib.camera((0, 0, 5), (0, 0, 0), ortho=1.0)
bpy.context.scene.camera.rotation_euler = (0, 0, 0)
bpy.context.scene.camera.data.ortho_scale = max(aspect, 1)

m = bpy.data.materials.new("smoke")
m.use_nodes = True
nt = m.node_tree
N = nt.nodes
L = nt.links
for n in list(N):
    if n.type != "OUTPUT_MATERIAL":
        N.remove(n)
outn = N["Material Output"]


def node(t, **kw):
    n = N.new(t)
    for k, v in kw.items():
        if k in n.inputs:
            n.inputs[k].default_value = v
        else:
            setattr(n, k, v)
    return n


def ramp(stops):
    r = node("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
    els[1].position, els[1].color = stops[-1][0], (*stops[-1][1], 1)
    for p, c in stops[1:-1]:
        e = els.new(p)
        e.color = (*c, 1)
    return r


tc = node("ShaderNodeTexCoord")
# 按画幅比例拉伸坐标，噪声才不会被压扁
scale_xy = node("ShaderNodeVectorMath", operation="MULTIPLY")
scale_xy.inputs[1].default_value = (aspect, 1, 0)
L.new(tc.outputs["Generated"], scale_xy.inputs[0])
# 平面的 Generated 坐标 z 恒为 0.5，遮罩只用 xy，所以先压平
flat = node("ShaderNodeVectorMath", operation="MULTIPLY")
flat.inputs[1].default_value = (1, 1, 0)
L.new(tc.outputs["Generated"], flat.inputs[0])

# 第一层噪声 → 偏移坐标（域扭曲）
warp = node("ShaderNodeTexNoise", **{"Scale": 1.6, "Detail": 6.0, "Roughness": 0.55})
L.new(scale_xy.outputs[0], warp.inputs["Vector"])
centered = node("ShaderNodeVectorMath", operation="SUBTRACT")
centered.inputs[1].default_value = (0.5, 0.5, 0.5)
L.new(warp.outputs["Color"], centered.inputs[0])
amount = node("ShaderNodeVectorMath", operation="SCALE")
amount.inputs["Scale"].default_value = 1.1
L.new(centered.outputs[0], amount.inputs[0])
warped = node("ShaderNodeVectorMath", operation="ADD")
L.new(scale_xy.outputs[0], warped.inputs[0])
L.new(amount.outputs[0], warped.inputs[1])

# 第二层噪声：烟雾 / 墨迹本体
body = node("ShaderNodeTexNoise", **{"Scale": 2.2, "Detail": 14.0, "Roughness": 0.62, "Distortion": 0.3})
L.new(warped.outputs[0], body.inputs["Vector"])

# 位置遮罩：night 在画面中右偏亮（给主视觉留光源）；day 只在右上和左下两角出现墨迹
mask_tc = node("ShaderNodeMapping")
L.new(flat.outputs[0], mask_tc.inputs["Vector"])
grad = node("ShaderNodeTexGradient", gradient_type="SPHERICAL")
L.new(mask_tc.outputs[0], grad.inputs["Vector"])
mix_mask = node("ShaderNodeMath", operation="MULTIPLY")
L.new(body.outputs["Fac"], mix_mask.inputs[0])

if variant == "night":
    # 遮罩中心放在画面 (0.62, 0.5)，即主视觉的位置；Mapping 先缩放再平移
    sx, sy = 1.25, 1.5
    mask_tc.inputs["Scale"].default_value = (sx, sy, 1)
    mask_tc.inputs["Location"].default_value = (-0.62 * sx, -0.5 * sy, 0)
    mask_r = ramp([(0.0, (0.35, 0.35, 0.35)), (0.55, (0.8, 0.8, 0.8)), (1.0, (1.0, 1.0, 1.0))])
    L.new(grad.outputs["Fac"], mask_r.inputs[0])
    L.new(mask_r.outputs["Color"], mix_mask.inputs[1])
    col = ramp([(0.0, (0.0008, 0.001, 0.002)), (0.24, (0.0012, 0.0016, 0.006)),
                (0.36, (0.003, 0.007, 0.05)), (0.46, (0.008, 0.026, 0.3)),
                (0.56, (0.03, 0.09, 0.85)), (0.66, (0.35, 0.45, 1.0)), (0.75, (0.85, 0.9, 1.0))])
else:
    # day：两个角各一团墨，中间留白
    mask_tc.inputs["Location"].default_value = (0, 0, 0)
    mask_tc.inputs["Scale"].default_value = (1, 1, 1)
    d = node("ShaderNodeVectorMath", operation="DISTANCE")
    d.inputs[1].default_value = (1.0, 1.0, 0)
    L.new(flat.outputs[0], d.inputs[0])
    d2 = node("ShaderNodeVectorMath", operation="DISTANCE")
    d2.inputs[1].default_value = (0.0, 0.0, 0)
    L.new(flat.outputs[0], d2.inputs[0])
    near = node("ShaderNodeMath", operation="MINIMUM")
    L.new(d.outputs["Value"], near.inputs[0])
    L.new(d2.outputs["Value"], near.inputs[1])
    mask_r = ramp([(0.0, (1.5, 1.5, 1.5)), (0.3, (1.15, 1.15, 1.15)), (0.62, (0.0, 0.0, 0.0))])
    L.new(near.outputs[0], mask_r.inputs[0])
    L.new(mask_r.outputs["Color"], mix_mask.inputs[1])
    col = ramp([(0.0, (0.86, 0.88, 0.91)), (0.36, (0.86, 0.88, 0.91)),
                (0.44, (0.45, 0.53, 0.95)), (0.52, (0.03, 0.09, 1.0)), (0.66, (0.004, 0.012, 0.2))])
L.new(mix_mask.outputs[0], col.inputs[0])

result = col.outputs["Color"]

if variant == "night":
    # 星尘：高频 Voronoi 取极近点，再用一层噪声控制疏密
    vor = node("ShaderNodeTexVoronoi", **{"Scale": 340.0, "Randomness": 1.0})
    L.new(scale_xy.outputs[0], vor.inputs["Vector"])
    star = node("ShaderNodeMapRange", **{"From Min": 0.06, "From Max": 0.0, "To Min": 0.0, "To Max": 1.0})
    L.new(vor.outputs["Distance"], star.inputs["Value"])
    pw = node("ShaderNodeMath", operation="POWER")
    pw.inputs[1].default_value = 6.0
    L.new(star.outputs["Result"], pw.inputs[0])
    dens = node("ShaderNodeTexNoise", **{"Scale": 3.0, "Detail": 2.0})
    L.new(scale_xy.outputs[0], dens.inputs["Vector"])
    dens_r = ramp([(0.45, (0, 0, 0)), (0.7, (1, 1, 1))])
    L.new(dens.outputs["Fac"], dens_r.inputs[0])
    sm = node("ShaderNodeMath", operation="MULTIPLY")
    L.new(pw.outputs[0], sm.inputs[0])
    L.new(dens_r.outputs["Color"], sm.inputs[1])
    star_col = node("ShaderNodeMix", data_type="RGBA", blend_type="ADD")
    star_col.inputs["Factor"].default_value = 1.0
    L.new(result, star_col.inputs["A"])
    tint = node("ShaderNodeCombineColor")
    L.new(sm.outputs[0], tint.inputs["Red"])
    L.new(sm.outputs[0], tint.inputs["Green"])
    L.new(sm.outputs[0], tint.inputs["Blue"])
    L.new(tint.outputs[0], star_col.inputs["B"])
    result = star_col.outputs["Result"]

em = node("ShaderNodeEmission", **{"Strength": 1.0})
L.new(result, em.inputs["Color"])
L.new(em.outputs[0], outn.inputs["Surface"])
plane.data.materials.append(m)

lib.save(out)
