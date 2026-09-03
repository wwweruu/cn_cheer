# -*- coding: utf-8 -*-
"""车-红方（汉军战车）样板建模脚本
规范：米制 / 原点在底座底面中心 / 面向 Blender -Y（导出 GLB 后为 three.js +Z）
输出：public/assets/models/chariot_red.glb + 三视图渲染 + .blend 工程
运行：blender --background --python build_chariot_red.py
"""
import bpy
import math
import os
from mathutils import Vector

ROOT = r"C:\Users\guyu\cn_cheer"
OUT_GLB = os.path.join(ROOT, "public", "assets", "models", "chariot_red.glb")
OUT_BLEND = os.path.join(ROOT, "blender", "chariot_red.blend")
RENDER_DIR = os.path.join(ROOT, "blender", "renders")
for d in (os.path.dirname(OUT_GLB), os.path.dirname(OUT_BLEND), RENDER_DIR):
    os.makedirs(d, exist_ok=True)

# ---------- 场景清理 ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------- 材质 ----------
def mat(name, color, metallic=0.0, roughness=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return m

MAT_WALNUT = mat("walnut_base", (0.16, 0.09, 0.05), 0.1, 0.55)      # 深胡桃木底座
MAT_RED    = mat("red_lacquer", (0.45, 0.09, 0.07), 0.25, 0.32)      # 朱红漆
MAT_GOLD   = mat("gilt_bronze", (0.72, 0.55, 0.28), 0.85, 0.22)      # 鎏金铜件
MAT_WOOD   = mat("aged_wood", (0.32, 0.20, 0.11), 0.05, 0.6)         # 木质
MAT_DARK   = mat("dark_iron", (0.12, 0.10, 0.10), 0.7, 0.35)         # 铁件
MAT_CLOTH  = mat("crimson_cloth", (0.38, 0.06, 0.06), 0.0, 0.75)     # 猩红织物
MAT_HORSE  = mat("horse_bay", (0.25, 0.13, 0.07), 0.0, 0.6)          # 枣红马
MAT_ARMOR  = mat("lamellar_red", (0.42, 0.12, 0.10), 0.55, 0.35)     # 红缘札甲
MAT_SKIN   = mat("skin", (0.55, 0.38, 0.28), 0.0, 0.55)

def assign(obj, material):
    obj.data.materials.append(material)
    return obj

def box(name, loc, scale, material, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (scale[0] / 2, scale[1] / 2, scale[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    if bevel > 0:
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return assign(o, material)

def cyl(name, loc, radius, depth, material, rot=(0, 0, 0), vertices=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth,
                                        location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    return assign(o, material)

def sph(name, loc, scale, material, seg=16, rings=10):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    return assign(o, material)

def cone(name, loc, r1, r2, depth, material, rot=(0, 0, 0), vertices=12):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=r1, radius2=r2,
                                    depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    return assign(o, material)

def torus(name, loc, major, minor, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=16, minor_segments=6,
                                     location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    return assign(o, material)

# ---------- 底座（直径0.92，厚0.184，红漆描边） ----------
base = cyl("base_walnut", (0, 0, 0.092), 0.46, 0.184, MAT_WALNUT, vertices=32)
torus("base_gold_ring", (0, 0, 0.175), 0.415, 0.018, MAT_RED)
torus("base_bottom_trim", (0, 0, 0.012), 0.435, 0.012, MAT_RED)

# 底座正面刻字“车”（描金），面朝 -Y
font_path = r"C:\Windows\Fonts\simkai.ttf"
if os.path.exists(font_path):
    bpy.ops.object.text_add(location=(0, -0.463, 0.092), rotation=(math.pi / 2, 0, 0))
    txt = bpy.context.active_object
    txt.name = "base_char_che"
    txt.data.body = "车"
    txt.data.font = bpy.data.fonts.load(font_path)
    txt.data.align_x = "CENTER"
    txt.data.align_y = "CENTER"
    txt.data.size = 0.11
    txt.data.extrude = 0.004
    assign(txt, MAT_GOLD)

Z0 = 0.184  # 底座顶面

# ---------- 车轮（轮毂/辐条分件，鎏金铜件） ----------
WHEEL_R = 0.30
WHEEL_Z = Z0 + WHEEL_R
AXLE_X = 0.36
for side, sx in (("L", -AXLE_X), ("R", AXLE_X)):
    torus(f"wheel_{side}_rim", (sx, 0, WHEEL_Z), WHEEL_R - 0.025, 0.032, MAT_WOOD, rot=(0, math.pi / 2, 0))
    cyl(f"wheel_{side}_hub", (sx, 0, WHEEL_Z), 0.055, 0.09, MAT_GOLD, rot=(0, math.pi / 2, 0))
    for i in range(10):
        a = i * math.pi / 5
        cyl(f"wheel_{side}_spoke_{i}",
            (sx, -math.cos(a) * WHEEL_R * 0.48, WHEEL_Z + math.sin(a) * WHEEL_R * 0.48),
            0.014, WHEEL_R - 0.06, MAT_WOOD, rot=(a, 0, 0), vertices=8)
cyl("axle", (0, 0, WHEEL_Z), 0.028, AXLE_X * 2 + 0.12, MAT_DARK, rot=(0, math.pi / 2, 0))

# ---------- 车厢（红漆、铆钉、云雷纹以饰条近似） ----------
CAB_Z = WHEEL_Z + 0.05
box("carriage_floor", (0, 0, CAB_Z + 0.03), (0.62, 0.52, 0.06), MAT_RED, bevel=0.01)
for sx in (-0.30, 0.30):
    box(f"carriage_side_{sx}", (sx, 0, CAB_Z + 0.16), (0.03, 0.52, 0.22), MAT_RED, bevel=0.008)
box("carriage_front", (0, -0.245, CAB_Z + 0.16), (0.62, 0.03, 0.22), MAT_RED, bevel=0.008)
box("carriage_back", (0, 0.245, CAB_Z + 0.16), (0.62, 0.03, 0.22), MAT_RED, bevel=0.008)
# 鎏金饰条与铆钉
box("carriage_trim_front", (0, -0.262, CAB_Z + 0.16), (0.5, 0.008, 0.03), MAT_GOLD)
for i in range(6):
    sph(f"rivet_f_{i}", (-0.25 + i * 0.1, -0.262, CAB_Z + 0.225), (0.012, 0.012, 0.012), MAT_GOLD, seg=8, rings=6)

# ---------- 车辕 + 横衡 ----------
cyl("shaft", (0, -0.62, WHEEL_Z + 0.04), 0.028, 0.85, MAT_RED, rot=(math.pi / 2, 0, 0))
cyl("heng_crossbar", (0, -1.02, WHEEL_Z + 0.02), 0.022, 0.78, MAT_WOOD, rot=(0, math.pi / 2, 0))

# ---------- 伞盖（红缨顶） ----------
cyl("canopy_pole", (0.0, 0.18, CAB_Z + 0.5), 0.016, 0.85, MAT_GOLD)
cone("canopy_top", (0.0, 0.18, CAB_Z + 0.95), 0.34, 0.03, 0.10, MAT_CLOTH, vertices=16)
torus("canopy_gold_edge", (0.0, 0.18, CAB_Z + 0.905), 0.325, 0.012, MAT_GOLD)
cone("canopy_tassel", (0.0, 0.18, CAB_Z + 1.04), 0.035, 0.0, 0.09, MAT_RED, vertices=10)

# ---------- 驾马 ×2（红缘马铠） ----------
def build_horse(prefix, x):
    y = -1.02
    body_z = Z0 + 0.42
    sph(f"{prefix}_body", (x, y, body_z), (0.14, 0.26, 0.155), MAT_HORSE)
    # 颈与头
    cyl(f"{prefix}_neck", (x, y - 0.24, body_z + 0.17), 0.07, 0.34, MAT_HORSE,
        rot=(0.7, 0, 0), vertices=10)
    box(f"{prefix}_head", (x, y - 0.42, body_z + 0.30), (0.11, 0.22, 0.13), MAT_HORSE, bevel=0.02)
    for ex in (-0.04, 0.04):
        cone(f"{prefix}_ear_{ex}", (x + ex, y - 0.40, body_z + 0.40), 0.02, 0.0, 0.07, MAT_HORSE, vertices=6)
    # 鬃毛
    box(f"{prefix}_mane", (x, y - 0.18, body_z + 0.30), (0.03, 0.28, 0.14), MAT_DARK, bevel=0.01)
    # 尾
    cone(f"{prefix}_tail", (x, y + 0.27, body_z - 0.02), 0.045, 0.012, 0.30, MAT_DARK,
         rot=(0.5, 0, 0), vertices=8)
    # 四腿
    for lx in (-0.07, 0.07):
        for ly in (-0.15, 0.15):
            cyl(f"{prefix}_leg_{lx}_{ly}", (x + lx, y + ly, Z0 + 0.19), 0.032, 0.38, MAT_HORSE, vertices=8)
            cyl(f"{prefix}_hoof_{lx}_{ly}", (x + lx, y + ly, Z0 + 0.02), 0.038, 0.045, MAT_DARK, vertices=8)
    # 马铠四件：面帘 / 鸡颈 / 当胸 / 搭后（红缘鎏金钉）
    box(f"{prefix}_armor_face", (x, y - 0.435, body_z + 0.30), (0.12, 0.05, 0.15), MAT_ARMOR, bevel=0.015)
    box(f"{prefix}_armor_neck", (x, y - 0.22, body_z + 0.13), (0.15, 0.16, 0.20), MAT_ARMOR, bevel=0.02)
    box(f"{prefix}_armor_chest", (x, y - 0.24, body_z - 0.02), (0.17, 0.06, 0.20), MAT_ARMOR, bevel=0.015)
    box(f"{prefix}_armor_rump", (x, y + 0.22, body_z + 0.03), (0.17, 0.14, 0.16), MAT_ARMOR, bevel=0.015)
    for dx in (-0.05, 0.05):
        sph(f"{prefix}_armor_stud_{dx}", (x + dx, y - 0.255, body_z + 0.12), (0.011, 0.011, 0.011), MAT_GOLD, seg=8, rings=6)
    # 鞍具
    box(f"{prefix}_saddle", (x, y, body_z + 0.15), (0.16, 0.18, 0.05), MAT_RED, bevel=0.015)
    torus(f"{prefix}_girth", (x, y, body_z - 0.01), 0.155, 0.014, MAT_DARK, rot=(0, 0, 0))

build_horse("horse_L", -0.30)
build_horse("horse_R", 0.30)

# ---------- 车兵（汉制重甲 A-pose，持长戈） ----------
SY = 0.05           # 站在车厢内
SZ = CAB_Z + 0.06   # 脚底
# 腿与战靴
for lx in (-0.07, 0.07):
    cyl(f"soldier_leg_{lx}", (lx, SY, SZ + 0.16), 0.038, 0.32, MAT_DARK, vertices=8)
    box(f"soldier_boot_{lx}", (lx, SY - 0.02, SZ + 0.02), (0.09, 0.14, 0.05), MAT_DARK, bevel=0.01)
# 甲裙 + 胸甲
cone("soldier_skirt", (0, SY, SZ + 0.40), 0.16, 0.115, 0.22, MAT_ARMOR, vertices=10)
box("soldier_cuirass", (0, SY, SZ + 0.60), (0.24, 0.15, 0.24), MAT_ARMOR, bevel=0.02)
box("soldier_plastron_gold", (0, SY - 0.078, SZ + 0.60), (0.14, 0.012, 0.16), MAT_GOLD, bevel=0.005)
# 披膊（肩甲）
for sx in (-0.15, 0.15):
    box(f"soldier_pauldron_{sx}", (sx, SY, SZ + 0.71), (0.10, 0.14, 0.07), MAT_ARMOR, bevel=0.015)
# 手臂 A-pose（水平）
for sx, sign in ((-1, -1), (1, 1)):
    cyl(f"soldier_arm_{sx}", (sign * 0.24, SY, SZ + 0.70), 0.030, 0.30, MAT_ARMOR,
        rot=(0, math.pi / 2, 0), vertices=8)
    sph(f"soldier_hand_{sx}", (sign * 0.40, SY, SZ + 0.70), (0.035, 0.035, 0.035), MAT_SKIN, seg=10, rings=8)
# 头 + 铁盔红缨
sph("soldier_head", (0, SY, SZ + 0.84), (0.075, 0.07, 0.085), MAT_SKIN)
cone("soldier_helmet", (0, SY, SZ + 0.91), 0.095, 0.05, 0.12, MAT_DARK, vertices=10)
cone("soldier_plume", (0, SY, SZ + 1.01), 0.03, 0.0, 0.12, MAT_RED, vertices=8)
# 长戈（右手侧垂直）
GE_X = 0.40
cyl("ge_pole", (GE_X, SY, SZ + 0.62), 0.014, 1.25, MAT_WOOD, vertices=8)
box("ge_blade", (GE_X, SY, SZ + 1.18), (0.05, 0.016, 0.16), MAT_GOLD, bevel=0.004)
box("ge_dagger_axis", (GE_X + 0.045, SY, SZ + 1.13), (0.10, 0.014, 0.035), MAT_GOLD, bevel=0.003)
cone("ge_tassel", (GE_X, SY, SZ + 1.10), 0.028, 0.0, 0.08, MAT_RED, rot=(math.pi, 0, 0), vertices=8)

# ---------- 导出 GLB ----------
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format="GLB",
    export_yup=True,
    export_apply=True,
    export_animations=False,
    export_materials="EXPORT",
)
print("GLB-EXPORTED", OUT_GLB)

# ---------- 渲染三视图（正交、棚光、灰底） ----------
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 768
scene.render.resolution_y = 1152
scene.render.film_transparent = False
world = bpy.data.worlds.new("studio")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.55, 0.55, 1.0)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0

def add_area(name, loc, energy, size=3.0):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    o = bpy.data.objects.new(name, data)
    scene.collection.objects.link(o)
    o.location = loc
    # 指向原点
    direction = Vector((0, 0, 0.7)) - o.location
    o.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

add_area("key", (2.5, -2.5, 3.5), 900)
add_area("fill", (-2.5, -1.5, 2.5), 600)
add_area("rim", (0, 2.8, 3.0), 700)

cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = 2.1
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.lens = 50

TARGET = Vector((0, -0.25, 0.85))
views = {
    "front": Vector((0, -4.2, 0.85)),
    "side": Vector((4.2, -0.25, 0.85)),
    "back": Vector((0, 3.8, 0.85)),
}
for name, loc in views.items():
    cam.location = loc
    cam.rotation_euler = (TARGET - loc).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(RENDER_DIR, f"chariot_red_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", scene.render.filepath)

print("DONE-ALL")
