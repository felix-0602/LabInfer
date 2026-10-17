"""Blender 渲染脚本共用的工具函数。

用法见 render.sh。每个场景脚本只负责搭场景，渲染设置、影棚灯光、材质都从这里取。
铬银和玻璃的质感几乎全部来自它们反射的环境，所以影棚 = 暗场 + 白色长条灯（锐利高光线）
+ 一块钴蓝大灯板（反射里的品牌色）。
"""
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

COBALT = (0.0129, 0.0436, 1.0)  # #1e3bff 的线性值
NIGHT = (0.0012, 0.0015, 0.0030)


def args():
    """读取 `blender -b -P scene.py -- out.png 1400 1800 256` 之后的参数。"""
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = a[0] if len(a) > 0 else "/tmp/out.png"
    w = int(a[1]) if len(a) > 1 else 1000
    h = int(a[2]) if len(a) > 2 else 1000
    samples = int(a[3]) if len(a) > 3 else 128
    return out, w, h, samples


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_render(w, h, samples, transparent=True, look="AgX - Medium High Contrast"):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == kind
                sc.cycles.device = "GPU"
                break
        except TypeError:
            continue
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 16
    sc.cycles.glossy_bounces = 8
    sc.cycles.transmission_bounces = 16
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.caustics_reflective = True
    sc.cycles.caustics_refractive = True
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.cycles.film_transparent_glass = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.render.image_settings.color_depth = "16"
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = look
    except TypeError:
        pass
    return sc


def world(color=NIGHT, strength=1.0):
    w = bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*color, 1)
    bg.inputs["Strength"].default_value = strength
    return w


def area_light(name, size, loc, target=(0, 0, 0), color=(1, 1, 1), energy=500.0):
    """矩形面光源。Cycles 中面光源在镜面反射里可见，所以它就是铬面上的高光条。"""
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "RECTANGLE"
    data.size, data.size_y = size
    data.color = color
    data.energy = energy
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    look_at(obj, target)
    return obj


def studio_world(variant="night", strength=1.0):
    """渐变天光环境：下暗、地平线一圈钴蓝、上方冷灰。它不会出现在画面背景里
    （film_transparent），只出现在铬面和玻璃的反射里，给大面积的明暗过渡。"""
    w = bpy.data.worlds.new("Studio")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs[0])
    els = ramp.color_ramp.elements
    if variant == "night":
        stops = [(0.0, (0.002, 0.002, 0.004)), (0.47, (0.004, 0.005, 0.012)),
                 (0.52, (0.02, 0.05, 0.6)), (0.6, (0.05, 0.055, 0.08)), (1.0, (0.9, 0.93, 1.0))]
    else:
        stops = [(0.0, (0.35, 0.37, 0.42)), (0.48, (0.6, 0.63, 0.7)),
                 (0.53, (0.1, 0.2, 1.0)), (0.6, (0.75, 0.78, 0.84)), (1.0, (1.0, 1.0, 1.0))]
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
    els[1].position, els[1].color = stops[-1][0], (*stops[-1][1], 1)
    for pos, col in stops[1:-1]:
        e = els.new(pos)
        e.color = (*col, 1)
    bg = nt.nodes["Background"]
    bg.inputs["Strength"].default_value = strength
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    return w


def studio(variant="night", strength=1.0):
    """影棚灯光。variant: night 暗场 / day 浅色页面。
    两块大柔光箱给大面积亮面，两条窄灯条给锐利高光线，钴蓝灯板给品牌色反射。"""
    k = strength
    studio_world(variant, 1.0)
    area_light("softbox_L", (3.5, 7), (-6, -4, 2.5), energy=2600 * k)
    area_light("softbox_top", (6, 3), (0, -2, 8), energy=1800 * k)
    area_light("strip_L", (0.4, 10), (-3, -7, 3), energy=700 * k)
    area_light("strip_R", (0.3, 10), (4.5, -5, 4), energy=650 * k)
    area_light("cobalt_panel", (7, 9), (7, 2, 0.5), color=COBALT, energy=(3200 if variant == "night" else 1500) * k)
    area_light("rim", (10, 1.2), (-1, 7, 3), color=(0.85, 0.9, 1.0), energy=900 * k)
    # 相机身后偏右的大补光：圆柱铬面正中会出现一片柔和的灰白渐变
    area_light("front_fill", (5, 12), (3.5, -16, 1.5), color=(0.9, 0.93, 1.0), energy=2200 * k)


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def camera(loc, target, lens=85, dof=None, ortho=None):
    data = bpy.data.cameras.new("Cam")
    data.lens = lens
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = ortho
    if dof:
        data.dof.use_dof = True
        data.dof.focus_distance, data.dof.aperture_fstop = dof
    cam = bpy.data.objects.new("Cam", data)
    bpy.context.collection.objects.link(cam)
    cam.location = loc
    look_at(cam, target)
    bpy.context.scene.camera = cam
    return cam


# ---------- 材质 ----------

def principled(name, **inputs):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    for k, v in inputs.items():
        p.inputs[k].default_value = v
    return m


def mat_silver(rough=0.035):
    return principled("silver", **{"Base Color": (0.93, 0.94, 0.96, 1), "Metallic": 1.0, "Roughness": rough})


def mat_glass(tint=(1, 1, 1), rough=0.0, ior=1.47):
    return principled("glass", **{"Base Color": (*tint, 1), "Transmission Weight": 1.0,
                                  "Roughness": rough, "IOR": ior, "Metallic": 0.0})


def mat_cobalt_glass(density=0.9):
    """钴蓝玻璃：表面是清玻璃，颜色来自体积吸收，厚的地方更蓝。"""
    m = mat_glass()
    nt = m.node_tree
    absorb = nt.nodes.new("ShaderNodeVolumeAbsorption")
    absorb.inputs["Color"].default_value = (0.05, 0.12, 1.0, 1)
    absorb.inputs["Density"].default_value = density
    nt.links.new(absorb.outputs[0], nt.nodes["Material Output"].inputs["Volume"])
    return m


def mat_emit(color, strength):
    m = bpy.data.materials.new("emit")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return m


# ---------- 几何 ----------

def mesh_obj(name, verts, faces, mat=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if smooth:
        for poly in me.polygons:
            poly.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    if mat:
        me.materials.append(mat)
    return obj


def lathe(name, profile, segs=128, mat=None, top_offset=None):
    """绕 Z 轴旋转 profile [(r, z), ...] 生成回转体。
    top_offset(angle) 可以让最上面一圈顶点按角度偏移高度，做出不规则边缘。"""
    verts, faces = [], []
    n = len(profile)
    for s in range(segs):
        a = 2 * math.pi * s / segs
        for i, (r, z) in enumerate(profile):
            if top_offset and i == n - 1:
                z += top_offset(a)
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for s in range(segs):
        s2 = (s + 1) % segs
        for i in range(n - 1):
            faces.append((s * n + i, s2 * n + i, s2 * n + i + 1, s * n + i + 1))
    return mesh_obj(name, verts, faces, mat)


def solidify(obj, thickness, offset=-1):
    m = obj.modifiers.new("solid", "SOLIDIFY")
    m.thickness = thickness
    m.offset = offset
    m.use_even_offset = True
    return m


def save(out):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
