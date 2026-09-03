# -*- coding: utf-8 -*-
"""玄甲棋局 · 14 枚棋子参数化建模工厂（一期 GLB 资产）
规范：米制 / 原点在底座底面中心 / 面向 Blender -Y（导出后 three.js +Z）
输出：public/assets/models/{type}_{camp}.glb + blender/pieces/*.blend + blender/renders/*.png
运行：blender --background --python build_all_pieces.py
"""
import bpy
import math
import os
from mathutils import Vector

ROOT = r"C:\Users\guyu\cn_cheer"
MODEL_DIR = os.path.join(ROOT, "public", "assets", "models")
BLEND_DIR = os.path.join(ROOT, "blender", "pieces")
RENDER_DIR = os.path.join(ROOT, "blender", "renders")
for d in (MODEL_DIR, BLEND_DIR, RENDER_DIR):
    os.makedirs(d, exist_ok=True)

Z0 = 0.184  # 底座顶面高度
PI = math.pi

# ---------------- 基础件 ----------------
def mat(name, color, metallic=0.0, roughness=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    return m

def make_theme(camp):
    red = camp == "red"
    return {
        "camp": camp,
        "walnut": mat("walnut", (0.16, 0.09, 0.05), 0.1, 0.55),
        "trim": mat("trim", (0.45, 0.09, 0.07) if red else (0.06, 0.06, 0.06), 0.25, 0.32),
        "char": mat("char", (0.72, 0.55, 0.28) if red else (0.35, 0.25, 0.12),
                    0.85 if red else 0.7, 0.22 if red else 0.5),
        "lacquer": mat("lacquer", (0.45, 0.09, 0.07) if red else (0.08, 0.07, 0.07), 0.3, 0.3),
        "metal": mat("metal", (0.72, 0.55, 0.28) if red else (0.35, 0.25, 0.12),
                     0.85 if red else 0.7, 0.22 if red else 0.5),
        "armor": mat("armor", (0.42, 0.12, 0.10) if red else (0.10, 0.09, 0.09), 0.55, 0.35),
        "armor2": mat("armor2", (0.55, 0.20, 0.14) if red else (0.16, 0.14, 0.12), 0.45, 0.42),
        "cloth": mat("cloth", (0.38, 0.06, 0.06) if red else (0.05, 0.05, 0.06), 0.0, 0.75),
        "wood": mat("wood", (0.32, 0.20, 0.11), 0.05, 0.6),
        "dark": mat("dark", (0.12, 0.10, 0.10), 0.7, 0.35),
        "horse": mat("horse", (0.25, 0.13, 0.07) if red else (0.14, 0.11, 0.09), 0.0, 0.6),
        "skin": mat("skin", (0.55, 0.38, 0.28), 0.0, 0.55),
        "bone": mat("bone", (0.72, 0.68, 0.58), 0.0, 0.5),
        "white": mat("white", (0.8, 0.8, 0.78), 0.0, 0.6),
    }

def assign(o, m):
    o.data.materials.append(m)
    return o

def box(name, loc, size, m, bevel=0.0, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    if bevel > 0:
        md = o.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = 2
    return assign(o, m)

def cyl(name, loc, r, depth, m, rot=(0, 0, 0), v=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=v, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    return assign(o, m)

def sph(name, loc, scale, m, seg=16, rings=10):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    return assign(o, m)

def cone(name, loc, r1, r2, depth, m, rot=(0, 0, 0), v=12):
    bpy.ops.mesh.primitive_cone_add(vertices=v, radius1=r1, radius2=r2, depth=depth,
                                    location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    return assign(o, m)

def tor(name, loc, major, minor, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=16, minor_segments=6,
                                     location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    return assign(o, m)

# ---------------- 底座（含楷书刻字） ----------------
FONT = r"C:\Windows\Fonts\simkai.ttf"
def build_base(char, t):
    cyl("base", (0, 0, 0.092), 0.46, 0.184, t["walnut"], v=32)
    tor("base_trim_top", (0, 0, 0.175), 0.415, 0.018, t["trim"])
    tor("base_trim_bottom", (0, 0, 0.012), 0.435, 0.012, t["trim"])
    if os.path.exists(FONT):
        bpy.ops.object.text_add(location=(0, -0.463, 0.092), rotation=(PI / 2, 0, 0))
        txt = bpy.context.active_object
        txt.name = "base_char"
        txt.data.body = char
        txt.data.font = bpy.data.fonts.load(FONT)
        txt.data.align_x = "CENTER"
        txt.data.align_y = "CENTER"
        txt.data.size = 0.11
        txt.data.extrude = 0.004
        assign(txt, t["char"])

# ---------------- 人偶（A-pose 基准，参数化部件） ----------------
def humanoid(p, t, x=0.0, y=0.0, s=1.0, helmet="tie", plume=None, robe=False,
             cape=None, beard=False, bun=False, heavy=False, trophy=False,
             robe_color=None):
    """在 (x,y) 处建 A-pose 人偶，脚底 z=Z0。返回手部锚点。"""
    armor = t["armor"]
    z = Z0
    # 腿 + 靴
    for lx in (-0.075, 0.075):
        cyl(f"{p}_leg_{lx}", (x + lx * s, y, z + 0.19 * s), 0.040 * s, 0.38 * s, t["dark"], v=8)
        box(f"{p}_boot_{lx}", (x + lx * s, y - 0.02 * s, z + 0.03 * s),
            (0.10 * s, 0.15 * s, 0.06 * s), t["dark"], bevel=0.01)
    if robe:
        # 深衣长袍：整体垂坠到脚面
        cone(f"{p}_robe", (x, y, z + 0.42 * s), 0.20 * s, 0.115 * s, 0.78 * s,
             robe_color or t["cloth"], v=12)
        box(f"{p}_chest", (x, y, z + 0.72 * s), (0.24 * s, 0.15 * s, 0.20 * s),
            robe_color or t["cloth"], bevel=0.02)
    else:
        cone(f"{p}_skirt", (x, y, z + 0.46 * s), 0.17 * s, 0.12 * s, 0.24 * s, armor, v=10)
        box(f"{p}_cuirass", (x, y, z + 0.68 * s), (0.26 * s, 0.16 * s, 0.26 * s), armor, bevel=0.02)
        # 胸甲饰板
        box(f"{p}_plastron", (x, y - 0.083 * s, z + 0.68 * s),
            (0.15 * s, 0.012 * s, 0.18 * s), t["metal"], bevel=0.005)
        if heavy:  # 重铠加铆钉
            for i in range(3):
                sph(f"{p}_stud_{i}", (x - 0.06 * s + i * 0.06 * s, y - 0.09 * s, z + 0.60 * s),
                    (0.012 * s,) * 3, t["metal"], seg=8, rings=6)
    # 披膊/肩甲（长袍文官不挂肩甲）
    if not robe:
        for sx in (-1, 1):
            box(f"{p}_pauldron_{sx}", (x + sx * 0.16 * s, y, z + 0.81 * s),
                (0.11 * s, 0.15 * s, 0.08 * s), t["armor2"], bevel=0.015)
    if trophy:  # 黑方左肩兽皮战利品
        sph(f"{p}_trophy", (x - 0.17 * s, y, z + 0.86 * s), (0.07 * s, 0.09 * s, 0.06 * s),
            t["bone"], seg=10, rings=8)
    # 手臂 A-pose
    hx = {}
    for sx in (-1, 1):
        cyl(f"{p}_arm_{sx}", (x + sx * 0.27 * s, y, z + 0.80 * s), 0.033 * s, 0.34 * s,
            t["armor2"], rot=(0, PI / 2, 0), v=8)
        sph(f"{p}_hand_{sx}", (x + sx * 0.455 * s, y, z + 0.80 * s), (0.038 * s,) * 3,
            t["skin"], seg=10, rings=8)
        hx[sx] = (x + sx * 0.455 * s, y, z + 0.80 * s)
    # 大袖（仕）
    if robe:
        for sx in (-1, 1):
            box(f"{p}_sleeve_{sx}", (x + sx * 0.30 * s, y, z + 0.68 * s),
                (0.20 * s, 0.12 * s, 0.30 * s), robe_color or t["cloth"], bevel=0.02)
    # 头
    sph(f"{p}_head", (x, y, z + 0.97 * s), (0.080 * s, 0.075 * s, 0.090 * s), t["skin"])
    # 头盔/冠
    hz = z + 1.05 * s
    if helmet == "mian":  # 冕冠：平顶 + 前后垂旒
        box(f"{p}_mian_board", (x, y, hz + 0.06 * s), (0.30 * s, 0.20 * s, 0.03 * s), t["dark"], bevel=0.008)
        cyl(f"{p}_mian_cap", (x, y, hz), 0.085 * s, 0.06 * s, t["lacquer"], v=10)
        for fy in (-0.09, 0.09):
            for i in range(5):
                bx = x - 0.10 * s + i * 0.05 * s
                cyl(f"{p}_liuli_{fy}_{i}", (bx, y + fy * s, hz + 0.02 * s), 0.004 * s,
                    0.10 * s, t["metal"], v=6)
    elif helmet == "shuang_ling":  # 双翎霸盔
        cone(f"{p}_kui", (x, y, hz), 0.11 * s, 0.05 * s, 0.14 * s, t["dark"], v=10)
        for sx in (-1, 1):
            cone(f"{p}_ling_{sx}", (x + sx * 0.05 * s, y + 0.10 * s, hz + 0.16 * s),
                 0.018 * s, 0.004 * s, 0.30 * s, t["cloth"], rot=(0.5, sx * 0.15, 0), v=6)
    elif helmet == "jinxian":  # 进贤冠
        box(f"{p}_jinxian", (x, y, hz + 0.02 * s), (0.16 * s, 0.18 * s, 0.09 * s), t["dark"], bevel=0.01)
        box(f"{p}_jinxian_ridge", (x, y, hz + 0.075 * s), (0.04 * s, 0.18 * s, 0.03 * s), t["metal"])
    elif helmet == "wuguan":  # 皮质武冠
        cyl(f"{p}_wuguan", (x, y, hz), 0.09 * s, 0.07 * s, t["wood"], v=10)
        tor(f"{p}_wuguan_band", (x, y, hz - 0.02 * s), 0.09 * s, 0.012 * s, t["dark"])
    elif helmet == "pibian":  # 皮弁
        cone(f"{p}_pibian", (x, y, hz), 0.09 * s, 0.06 * s, 0.08 * s, t["wood"], v=10)
    elif helmet == "tie":  # 铁盔 + 盔缨
        cone(f"{p}_tiekui", (x, y, hz), 0.10 * s, 0.05 * s, 0.13 * s, t["dark"], v=10)
        if plume:
            cone(f"{p}_plume", (x, y, hz + 0.11 * s), 0.032 * s, 0.0, 0.13 * s, plume, v=8)
    if bun:  # 束发
        sph(f"{p}_bun", (x, y + 0.02 * s, hz), (0.04 * s,) * 3, t["dark"], seg=8, rings=6)
    if beard:  # 长须
        cone(f"{p}_beard", (x, y - 0.075 * s, z + 0.82 * s), 0.035 * s, 0.008 * s,
             0.22 * s, t["dark"], rot=(0.1, 0, 0), v=8)
    if cape:  # 披风/大氅
        cone(f"{p}_cape", (x, y + 0.10 * s, z + 0.55 * s),
             (0.30 if cape == "cloak" else 0.22) * s, 0.13 * s, 0.75 * s,
             t["cloth"], v=10)
        box(f"{p}_cape_top", (x, y + 0.06 * s, z + 0.88 * s),
            (0.26 * s, 0.08 * s, 0.06 * s), t["cloth"], bevel=0.02)
    return hx

# ---------------- 手持/腰挂武器 ----------------
def sword_waist(p, t, x, y, s=1.0, heavy=False):
    w = 0.045 if heavy else 0.032
    box(f"{p}_sword_blade", (x - 0.16 * s, y - 0.06 * s, Z0 + 0.45 * s),
        (w * s, 0.014 * s, 0.55 * s), t["metal"], bevel=0.003, rot=(0, 0, 0.1))
    box(f"{p}_sword_hilt", (x - 0.19 * s, y - 0.06 * s, Z0 + 0.75 * s),
        (0.03 * s, 0.03 * s, 0.12 * s), t["dark"], bevel=0.005)

def flag_waist(p, t, x, y, s=1.0):
    cyl(f"{p}_flagpole", (x + 0.17 * s, y - 0.04 * s, Z0 + 0.62 * s), 0.010 * s, 0.42 * s,
        t["wood"], v=6)
    box(f"{p}_flag", (x + 0.17 * s, y - 0.03 * s, Z0 + 0.78 * s),
        (0.02 * s, 0.14 * s, 0.16 * s), t["cloth"], bevel=0.004)

def spear(p, t, hand, s=1.0, tip=None):
    x, y, z = hand
    cyl(f"{p}_spear", (x, y, z + 0.35 * s), 0.016 * s, 1.35 * s, t["wood"], v=8)
    cone(f"{p}_spear_tip", (x, y, z + 1.08 * s), 0.035 * s, 0.0, 0.16 * s,
         tip or t["metal"], v=8)
    cone(f"{p}_spear_tassel", (x, y, z + 0.96 * s), 0.030 * s, 0.0, 0.09 * s,
         t["cloth"], rot=(PI, 0, 0), v=8)

def ge(p, t, hand, s=1.0):
    x, y, z = hand
    cyl(f"{p}_ge_pole", (x, y, z + 0.35 * s), 0.014 * s, 1.25 * s, t["wood"], v=8)
    box(f"{p}_ge_blade", (x, y, z + 0.92 * s), (0.05 * s, 0.016 * s, 0.16 * s), t["metal"], bevel=0.004)
    box(f"{p}_ge_ji", (x + 0.045 * s, y, z + 0.87 * s), (0.10 * s, 0.014 * s, 0.035 * s),
        t["metal"], bevel=0.003)
    cone(f"{p}_ge_tassel", (x, y, z + 0.80 * s), 0.028 * s, 0.0, 0.08 * s,
         t["cloth"], rot=(PI, 0, 0), v=8)

def dao(p, t, hand, s=1.0, short=False):
    x, y, z = hand
    L = 0.42 if short else 0.55
    box(f"{p}_dao_blade", (x, y, z - 0.30 * s), (0.045 * s, 0.014 * s, L * s),
        t["metal"], bevel=0.003)
    if not short:
        tor(f"{p}_dao_ring", (x, y, z + 0.02 * s), 0.030 * s, 0.008 * s, t["metal"])

def torch(p, t, hand, s=1.0):
    x, y, z = hand
    cyl(f"{p}_torch", (x, y, z - 0.25 * s), 0.016 * s, 0.5 * s, t["wood"], v=8)
    cone(f"{p}_torch_head", (x, y, z - 0.52 * s), 0.035 * s, 0.02 * s, 0.08 * s, t["dark"], v=8)

def fan(p, t, hand, s=1.0):
    x, y, z = hand
    cone(f"{p}_fan", (x, y - 0.05 * s, z - 0.02 * s), 0.16 * s, 0.03 * s, 0.30 * s,
         t["white"], rot=(PI / 2, 0, 0), v=10)
    cyl(f"{p}_fan_stem", (x, y, z - 0.15 * s), 0.010 * s, 0.18 * s, t["wood"], v=6)

def shield_round(p, t, hand, s=1.0, hide=False):
    x, y, z = hand
    m = t["wood"] if hide else t["lacquer"]
    cyl(f"{p}_shield", (x, y, z - 0.10 * s), 0.20 * s, 0.03 * s, m, rot=(0, PI / 2, 0), v=16)
    sph(f"{p}_shield_boss", (x - 0.02 * s, y, z - 0.10 * s), (0.03 * s, 0.05 * s, 0.05 * s),
        t["metal"], seg=8, rings=6)

def bow(p, t, hand, s=1.0):
    x, y, z = hand
    tor(f"{p}_bow", (x, y, z), 0.14 * s, 0.010 * s, t["wood"], rot=(0, PI / 2, 0))
    cyl(f"{p}_bow_string", (x + 0.14 * s, y, z), 0.002 * s, 0.26 * s, t["white"], v=4)

# ---------------- 马 ----------------
def horse(p, t, x, y, s=1.0, armor_tone=None, pouch=False):
    bz = Z0 + 0.42 * s
    am = armor_tone or t["armor"]
    sph(f"{p}_body", (x, y, bz), (0.14 * s, 0.26 * s, 0.155 * s), t["horse"])
    cyl(f"{p}_neck", (x, y - 0.24 * s, bz + 0.17 * s), 0.07 * s, 0.34 * s, t["horse"],
        rot=(0.7, 0, 0), v=10)
    box(f"{p}_head", (x, y - 0.42 * s, bz + 0.30 * s), (0.11 * s, 0.22 * s, 0.13 * s),
        t["horse"], bevel=0.02)
    for ex in (-0.04, 0.04):
        cone(f"{p}_ear_{ex}", (x + ex * s, y - 0.40 * s, bz + 0.40 * s),
             0.02 * s, 0.0, 0.07 * s, t["horse"], v=6)
    box(f"{p}_mane", (x, y - 0.18 * s, bz + 0.30 * s), (0.03 * s, 0.28 * s, 0.14 * s),
        t["dark"], bevel=0.01)
    cone(f"{p}_tail", (x, y + 0.27 * s, bz - 0.02 * s), 0.045 * s, 0.012 * s, 0.30 * s,
         t["dark"], rot=(0.5, 0, 0), v=8)
    for lx in (-0.07, 0.07):
        for ly in (-0.15, 0.15):
            cyl(f"{p}_leg_{lx}_{ly}", (x + lx * s, y + ly * s, Z0 + 0.19 * s),
                0.032 * s, 0.38 * s, t["horse"], v=8)
            cyl(f"{p}_hoof_{lx}_{ly}", (x + lx * s, y + ly * s, Z0 + 0.02 * s),
                0.038 * s, 0.045 * s, t["dark"], v=8)
    # 马铠四件
    box(f"{p}_armor_face", (x, y - 0.435 * s, bz + 0.30 * s), (0.12 * s, 0.05 * s, 0.15 * s), am, bevel=0.015)
    box(f"{p}_armor_neck", (x, y - 0.22 * s, bz + 0.13 * s), (0.15 * s, 0.16 * s, 0.20 * s), am, bevel=0.02)
    box(f"{p}_armor_chest", (x, y - 0.24 * s, bz - 0.02 * s), (0.17 * s, 0.06 * s, 0.20 * s), am, bevel=0.015)
    box(f"{p}_armor_rump", (x, y + 0.22 * s, bz + 0.03 * s), (0.17 * s, 0.14 * s, 0.16 * s), am, bevel=0.015)
    sph(f"{p}_armor_stud", (x, y - 0.255 * s, bz + 0.12 * s), (0.011 * s,) * 3, t["metal"], seg=8, rings=6)
    box(f"{p}_saddle", (x, y, bz + 0.15 * s), (0.16 * s, 0.18 * s, 0.05 * s), t["lacquer"], bevel=0.015)
    tor(f"{p}_girth", (x, y, bz - 0.01 * s), 0.155 * s, 0.014 * s, t["dark"])
    if pouch:  # 兽皮囊袋
        sph(f"{p}_pouch", (x + 0.15 * s, y + 0.05 * s, bz + 0.10 * s),
            (0.05 * s, 0.07 * s, 0.06 * s), t["bone"], seg=8, rings=6)
    return bz  # 马背高度

# ---------------- 象 ----------------
def elephant(p, t, s=1.0, wild=False):
    ez = Z0 + 0.60 * s
    for lx in (-0.16, 0.16):
        for ly in (-0.25, 0.25):
            cyl(f"{p}_leg_{lx}_{ly}", (lx * s, ly * s, Z0 + 0.28 * s), 0.075 * s, 0.56 * s,
                t["horse"] if wild else t["dark"], v=10)
    sph(f"{p}_body", (0, 0.02 * s, ez), (0.30 * s, 0.44 * s, 0.30 * s),
        t["horse"] if wild else t["dark"])
    sph(f"{p}_head", (0, -0.46 * s, ez + 0.05 * s), (0.17 * s, 0.18 * s, 0.17 * s),
        t["horse"] if wild else t["dark"])
    for ex in (-1, 1):  # 耳
        sph(f"{p}_ear_{ex}", (ex * 0.18 * s, -0.44 * s, ez + 0.10 * s),
            (0.05 * s, 0.12 * s, 0.14 * s), t["horse"] if wild else t["dark"], seg=10, rings=8)
    # 象牙（黑方加长）
    tl = 0.28 if wild else 0.20
    for tx in (-1, 1):
        cone(f"{p}_tusk_{tx}", (tx * 0.08 * s, -0.62 * s, ez - 0.06 * s),
             0.025 * s, 0.006 * s, tl * s, t["white"], rot=(1.9, 0, 0), v=8)
        cone(f"{p}_tuskcap_{tx}", (tx * 0.08 * s, -0.68 * s, ez - 0.12 * s),
             0.016 * s, 0.004 * s, 0.08 * s, t["metal"], rot=(1.9, 0, 0), v=8)
    # 象鼻（三段锥下垂微弯）
    cone(f"{p}_trunk1", (0, -0.56 * s, ez - 0.10 * s), 0.06 * s, 0.045 * s, 0.20 * s,
         t["horse"] if wild else t["dark"], rot=(0.5, 0, 0), v=10)
    cone(f"{p}_trunk2", (0, -0.62 * s, ez - 0.26 * s), 0.045 * s, 0.032 * s, 0.16 * s,
         t["horse"] if wild else t["dark"], rot=(0.15, 0, 0), v=10)
    cone(f"{p}_trunk3", (0, -0.63 * s, ez - 0.40 * s), 0.032 * s, 0.020 * s, 0.14 * s,
         t["horse"] if wild else t["dark"], v=10)
    # 象尾
    cone(f"{p}_tail", (0, 0.47 * s, ez - 0.10 * s), 0.03 * s, 0.008 * s, 0.30 * s,
         t["dark"], rot=(-0.3, 0, 0), v=8)
    # 象身护甲（额/颈/身侧，红鎏金饰边 / 黑青铜锈）
    am = t["armor"]
    box(f"{p}_armor_brow", (0, -0.52 * s, ez + 0.16 * s), (0.24 * s, 0.16 * s, 0.06 * s), am, bevel=0.015)
    for sx in (-1, 1):
        box(f"{p}_armor_side_{sx}", (sx * 0.26 * s, 0, ez + 0.02 * s),
            (0.05 * s, 0.55 * s, 0.30 * s), am, bevel=0.02)
        for i in range(4):
            sph(f"{p}_astud_{sx}_{i}", (sx * 0.285 * s, -0.20 * s + i * 0.13 * s, ez + 0.10 * s),
                (0.012 * s,) * 3, t["metal"], seg=8, rings=6)
    if wild:  # 白色图腾纹样（饰条近似）
        box(f"{p}_totem", (0, -0.545 * s, ez + 0.05 * s), (0.06 * s, 0.012 * s, 0.20 * s), t["white"])
    # 象鞍固定带
    tor(f"{p}_girth", (0, 0.02 * s, ez - 0.05 * s), 0.33 * s, 0.016 * s, t["dark"])
    # 鞍垫（连接象背与战楼）
    box(f"{p}_howdah_pad", (0, 0.02 * s, ez + 0.26 * s), (0.48 * s, 0.50 * s, 0.06 * s),
        t["cloth"], bevel=0.01)
    # 战楼
    tz = ez + 0.30 * s
    box(f"{p}_tower_floor", (0, 0.02 * s, tz), (0.44 * s, 0.44 * s, 0.04 * s), t["wood"], bevel=0.008)
    for cx in (-0.20, 0.20):
        for cy in (-0.18, 0.22):
            cyl(f"{p}_tower_post_{cx}_{cy}", (cx * s, cy * s, tz + 0.14 * s),
                0.014 * s, 0.28 * s, t["wood"], v=6)
    if wild:  # 黑羽 + 兽骨
        for cx in (-0.20, 0.20):
            cone(f"{p}_feather_{cx}", (cx * s, 0.22 * s, tz + 0.36 * s), 0.02 * s, 0.0,
                 0.16 * s, t["cloth"], v=6)
        sph(f"{p}_skull", (0, -0.20 * s, tz + 0.30 * s), (0.05 * s,) * 3, t["bone"], seg=8, rings=6)
    else:  # 红色幔帐 + 小旗
        for sx in (-1, 1):
            box(f"{p}_curtain_{sx}", (sx * 0.20 * s, 0.02 * s, tz + 0.12 * s),
                (0.02 * s, 0.40 * s, 0.20 * s), t["cloth"], bevel=0.004)
        cyl(f"{p}_flagpole", (0.20 * s, 0.22 * s, tz + 0.36 * s), 0.008 * s, 0.20 * s, t["wood"], v=6)
        box(f"{p}_flag", (0.20 * s, 0.24 * s, tz + 0.42 * s), (0.015 * s, 0.10 * s, 0.08 * s), t["cloth"])
    # 弓手
    hh = humanoid(f"{p}_archer", t, x=0, y=0.02 * s, s=0.52 * s, helmet="tie",
                  plume=t["cloth"])
    # 弓手脚底要落在战楼地板上：humanoid 从 Z0 起，战楼更高——整体抬高
    for o in bpy.context.scene.objects:
        if o.name.startswith(f"{p}_archer"):
            o.location.z += tz + 0.02 * s - Z0
    bow(f"{p}_bow", t, (hh[-1][0], hh[-1][1], hh[-1][2] + tz + 0.02 * s - Z0), s=0.6 * s)

print("factory-loaded")
