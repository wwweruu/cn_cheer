# -*- coding: utf-8 -*-
"""批量构建 14 枚棋子 GLB + 渲染质检图"""
import bpy
import math
import os
import sys
from mathutils import Vector

ROOT = r"C:\Users\guyu\cn_cheer"
sys.path.insert(0, os.path.join(ROOT, "blender"))
from piece_factory import (  # noqa: E402
    ROOT, MODEL_DIR, BLEND_DIR, RENDER_DIR, Z0, PI,
    make_theme, build_base, humanoid, horse, elephant,
    sword_waist, flag_waist, spear, ge, dao, torch, fan, shield_round,
    box, cyl, sph, cone, tor,
)

# ---------------- 骑手（坐姿） ----------------
def rider(p, t, x, y, saddle_z, s=0.8, plume=None, heavy=False):
    hip = saddle_z + 0.10 * s
    for sx in (-1, 1):
        # 大腿前伸、小腿下垂
        cyl(f"{p}_thigh_{sx}", (x + sx * 0.09 * s, y - 0.10 * s, hip - 0.03 * s),
            0.045 * s, 0.28 * s, t["armor2"], rot=(1.25, 0, 0), v=8)
        cyl(f"{p}_calf_{sx}", (x + sx * 0.09 * s, y - 0.20 * s, hip - 0.22 * s),
            0.035 * s, 0.26 * s, t["dark"], v=8)
    cone(f"{p}_skirt", (x, y, hip + 0.06 * s), 0.16 * s, 0.11 * s, 0.18 * s, t["armor"], v=10)
    box(f"{p}_cuirass", (x, y, hip + 0.24 * s), (0.25 * s, 0.16 * s, 0.24 * s), t["armor"], bevel=0.02)
    box(f"{p}_plastron", (x, y - 0.083 * s, hip + 0.24 * s), (0.14 * s, 0.012 * s, 0.16 * s),
        t["metal"], bevel=0.005)
    for sx in (-1, 1):
        box(f"{p}_pauldron_{sx}", (x + sx * 0.15 * s, y, hip + 0.36 * s),
            (0.10 * s, 0.14 * s, 0.07 * s), t["armor2"], bevel=0.015)
        cyl(f"{p}_arm_{sx}", (x + sx * 0.26 * s, y, hip + 0.35 * s), 0.032 * s, 0.32 * s,
            t["armor2"], rot=(0, PI / 2, 0), v=8)
        sph(f"{p}_hand_{sx}", (x + sx * 0.43 * s, y, hip + 0.35 * s), (0.036 * s,) * 3,
            t["skin"], seg=10, rings=8)
    sph(f"{p}_head", (x, y, hip + 0.50 * s), (0.078 * s, 0.073 * s, 0.088 * s), t["skin"])
    cone(f"{p}_kui", (x, y, hip + 0.58 * s), 0.10 * s, 0.05 * s, 0.13 * s, t["dark"], v=10)
    if plume:
        cone(f"{p}_plume", (x, y, hip + 0.68 * s), 0.032 * s, 0.0, 0.13 * s, plume, v=8)
    return (x + 0.43 * s, y, hip + 0.35 * s)  # 右手锚点

# ---------------- 战车 ----------------
def chariot(p, t, black=False):
    WHEEL_R, WHEEL_Z, AXLE_X = 0.30, Z0 + 0.30, 0.36
    for side, sx in (("L", -AXLE_X), ("R", AXLE_X)):
        tor(f"{p}_wheel_{side}_rim", (sx, 0, WHEEL_Z), WHEEL_R - 0.025, 0.032, t["wood"],
            rot=(0, PI / 2, 0))
        cyl(f"{p}_wheel_{side}_hub", (sx, 0, WHEEL_Z), 0.055, 0.09, t["metal"],
            rot=(0, PI / 2, 0))
        for i in range(10):
            a = i * PI / 5
            cyl(f"{p}_wheel_{side}_spoke_{i}",
                (sx, -math.cos(a) * WHEEL_R * 0.48, WHEEL_Z + math.sin(a) * WHEEL_R * 0.48),
                0.014, WHEEL_R - 0.06, t["wood"], rot=(a, 0, 0), v=8)
    cyl(f"{p}_axle", (0, 0, WHEEL_Z), 0.028, AXLE_X * 2 + 0.12, t["dark"], rot=(0, PI / 2, 0))
    CAB_Z = WHEEL_Z + 0.05
    box(f"{p}_floor", (0, 0, CAB_Z + 0.03), (0.62, 0.52, 0.06), t["lacquer"], bevel=0.01)
    for sx in (-0.30, 0.30):
        box(f"{p}_side_{sx}", (sx, 0, CAB_Z + 0.16), (0.03, 0.52, 0.22), t["lacquer"], bevel=0.008)
    box(f"{p}_front", (0, -0.245, CAB_Z + 0.16), (0.62, 0.03, 0.22), t["lacquer"], bevel=0.008)
    box(f"{p}_back", (0, 0.245, CAB_Z + 0.16), (0.62, 0.03, 0.22), t["lacquer"], bevel=0.008)
    box(f"{p}_trim_f", (0, -0.262, CAB_Z + 0.16), (0.5, 0.008, 0.03), t["metal"])
    if black:  # 饕餮纹以横向饰条近似
        box(f"{p}_taotie1", (0, -0.262, CAB_Z + 0.10), (0.4, 0.008, 0.02), t["metal"])
        box(f"{p}_taotie2", (0, -0.262, CAB_Z + 0.22), (0.4, 0.008, 0.02), t["metal"])
    for i in range(6):
        sph(f"{p}_rivet_{i}", (-0.25 + i * 0.1, -0.262, CAB_Z + 0.225), (0.012,) * 3,
            t["metal"], seg=8, rings=6)
    cyl(f"{p}_shaft", (0, -0.62, WHEEL_Z + 0.04), 0.028, 0.85, t["lacquer"], rot=(PI / 2, 0, 0))
    cyl(f"{p}_heng", (0, -1.02, WHEEL_Z + 0.02), 0.022, 0.78, t["wood"], rot=(0, PI / 2, 0))
    # 伞盖：红缨 / 黑羽
    cyl(f"{p}_canopy_pole", (0.0, 0.18, CAB_Z + 0.5), 0.016, 0.85, t["metal"])
    cone(f"{p}_canopy", (0.0, 0.18, CAB_Z + 0.95), 0.34, 0.03, 0.10, t["cloth"], v=16)
    tor(f"{p}_canopy_edge", (0.0, 0.18, CAB_Z + 0.905), 0.325, 0.012, t["metal"])
    if black:
        for i in range(3):
            cone(f"{p}_cfeather_{i}", (0.0, 0.18, CAB_Z + 1.06), 0.020, 0.0, 0.12,
                 t["cloth"], rot=(0.3, i * 2.1, 0), v=6)
    else:
        cone(f"{p}_tassel", (0.0, 0.18, CAB_Z + 1.04), 0.035, 0.0, 0.09, t["lacquer"], v=10)
    horse(f"{p}_horse_L", t, -0.30, -1.02, armor_tone=t["armor2"] if black else None,
          pouch=black)
    horse(f"{p}_horse_R", t, 0.30, -1.02, armor_tone=t["armor2"] if black else None,
          pouch=black)
    SY, SZ = 0.05, CAB_Z + 0.06
    for lx in (-0.07, 0.07):
        cyl(f"{p}_soldier_leg_{lx}", (lx, SY, SZ + 0.16), 0.038, 0.32, t["dark"], v=8)
        box(f"{p}_soldier_boot_{lx}", (lx, SY - 0.02, SZ + 0.02), (0.09, 0.14, 0.05),
            t["dark"], bevel=0.01)
    cone(f"{p}_soldier_skirt", (0, SY, SZ + 0.40), 0.16, 0.115, 0.22, t["armor"], v=10)
    box(f"{p}_soldier_cuirass", (0, SY, SZ + 0.60), (0.24, 0.15, 0.24), t["armor"], bevel=0.02)
    box(f"{p}_soldier_plastron", (0, SY - 0.078, SZ + 0.60), (0.14, 0.012, 0.16),
        t["metal"], bevel=0.005)
    for sx in (-1, 1):
        box(f"{p}_soldier_pauldron_{sx}", (sx * 0.15, SY, SZ + 0.71), (0.10, 0.14, 0.07),
            t["armor2"], bevel=0.015)
        cyl(f"{p}_soldier_arm_{sx}", (sx * 0.24, SY, SZ + 0.70), 0.030, 0.30,
            t["armor2"], rot=(0, PI / 2, 0), v=8)
        sph(f"{p}_soldier_hand_{sx}", (sx * 0.40, SY, SZ + 0.70), (0.035,) * 3,
            t["skin"], seg=10, rings=8)
    sph(f"{p}_soldier_head", (0, SY, SZ + 0.84), (0.075, 0.07, 0.085), t["skin"])
    cone(f"{p}_soldier_helmet", (0, SY, SZ + 0.91), 0.095, 0.05, 0.12, t["dark"], v=10)
    cone(f"{p}_soldier_plume", (0, SY, SZ + 1.01), 0.03, 0.0, 0.12, t["cloth"], v=8)
    ge(f"{p}", t, (0.40, SY, SZ + 0.70))

# ---------------- 火炮（红） ----------------
def cannon_red(p, t):
    # 炮架双轮
    for sx in (-0.20, 0.20):
        cyl(f"{p}_wheel_{sx}", (sx, 0.05, Z0 + 0.16), 0.16, 0.05, t["wood"],
            rot=(0, PI / 2, 0), v=16)
        cyl(f"{p}_hub_{sx}", (sx, 0.05, Z0 + 0.16), 0.04, 0.07, t["metal"],
            rot=(0, PI / 2, 0))
    # 炮架支臂
    for sx in (-0.16, 0.16):
        box(f"{p}_cheek_{sx}", (sx, 0.02, Z0 + 0.30), (0.05, 0.70, 0.12), t["wood"],
            bevel=0.01, rot=(0.1, 0, 0))
        box(f"{p}_trail_{sx}", (sx, 0.38, Z0 + 0.16), (0.05, 0.45, 0.08), t["wood"],
            bevel=0.01, rot=(-0.35, 0, 0))
    # 青铜炮身（微上扬、龙纹以鎏金箍带近似）
    cyl(f"{p}_barrel", (0, -0.05, Z0 + 0.42), 0.095, 0.80, t["metal"],
        rot=(PI / 2 - 0.08, 0, 0), v=16)
    tor(f"{p}_muzzle", (0, -0.44, Z0 + 0.455), 0.095, 0.022, t["metal"], rot=(0.08, 0, 0))
    for i, by in enumerate((-0.25, -0.02, 0.20)):
        tor(f"{p}_band_{i}", (0, by, Z0 + 0.42 + (0.02 - by) * 0.0), 0.098, 0.012,
            t["trim"], rot=(0.08, 0, 0))
    # 炮尾石兽镇钮
    sph(f"{p}_beast", (0, 0.38, Z0 + 0.48), (0.07, 0.09, 0.07), t["walnut"], seg=10, rings=8)
    box(f"{p}_beast_base", (0, 0.38, Z0 + 0.42), (0.10, 0.10, 0.04), t["walnut"], bevel=0.01)
    # 点火军士 + 火把 + 火药罐 + 铁弹丸
    hh = humanoid(f"{p}_crew", t, x=-0.34, y=0.10, helmet="tie", plume=t["cloth"])
    torch(f"{p}", t, hh[1])
    cyl(f"{p}_keg1", (0.28, -0.28, Z0 + 0.08), 0.07, 0.16, t["wood"], v=10)
    cyl(f"{p}_keg2", (0.36, -0.14, Z0 + 0.06), 0.055, 0.12, t["wood"], v=10)
    for i in range(3):
        sph(f"{p}_shot_{i}", (0.18 + i * 0.09, -0.36, Z0 + 0.035), (0.035,) * 3,
            t["dark"], seg=10, rings=8)

# ---------------- 抛石机（黑） ----------------
def trebuchet(p, t):
    # A 字桁架两侧
    for sx in (-0.22, 0.22):
        box(f"{p}_frame_a_{sx}", (sx, -0.10, Z0 + 0.33), (0.05, 0.06, 0.70), t["wood"],
            bevel=0.008, rot=(0.35, 0, 0))
        box(f"{p}_frame_b_{sx}", (sx, 0.14, Z0 + 0.33), (0.05, 0.06, 0.70), t["wood"],
            bevel=0.008, rot=(-0.35, 0, 0))
        box(f"{p}_base_beam_{sx}", (sx, 0.02, Z0 + 0.04), (0.07, 0.70, 0.08), t["wood"], bevel=0.008)
    cyl(f"{p}_pivot", (0, 0.02, Z0 + 0.62), 0.025, 0.56, t["dark"], rot=(0, PI / 2, 0))
    # 抛臂竖直向上，皮兜在顶端
    cyl(f"{p}_arm", (0, 0.02, Z0 + 0.85), 0.022, 1.30, t["wood"], v=8)
    sph(f"{p}_sling", (0, 0.02, Z0 + 1.52), (0.05, 0.05, 0.03), t["dark"], seg=8, rings=6)
    # 配重石箱（悬于短端——静态表现挂在臂后下方）
    box(f"{p}_counter", (0, 0.02, Z0 + 0.30), (0.22, 0.18, 0.20), t["walnut"], bevel=0.015)
    cyl(f"{p}_counter_rope", (0, 0.02, Z0 + 0.48), 0.008, 0.22, t["dark"], v=6)
    # 绞盘与绳索
    cyl(f"{p}_winch", (0, -0.30, Z0 + 0.12), 0.05, 0.30, t["wood"], rot=(0, PI / 2, 0), v=10)
    cyl(f"{p}_rope", (0, -0.16, Z0 + 0.35), 0.006, 0.55, t["dark"], rot=(0.6, 0, 0), v=6)
    # 石弹
    for i in range(3):
        sph(f"{p}_stone_{i}", (0.30 - i * 0.11, -0.36, Z0 + 0.045), (0.045,) * 3,
            t["bone"], seg=10, rings=8)
    # 操作军士
    hh = humanoid(f"{p}_crew", t, x=-0.36, y=0.05, helmet="wuguan", trophy=True)
    torch(f"{p}", t, hh[1])

# ---------------- 各棋子构建 ----------------
def b_general_red(t):
    humanoid("g", t, helmet="mian", cape="cape", heavy=True)
    sword_waist("g", t, 0, 0)
    flag_waist("g", t, 0, 0)
    box("g_tally", (0.09, -0.10, Z0 + 0.52), (0.05, 0.03, 0.08), t["metal"], bevel=0.005)  # 兵符
    cone("g_tassel", (0.09, -0.10, Z0 + 0.44), 0.02, 0.0, 0.06, t["cloth"], rot=(PI, 0, 0), v=6)

def b_general_black(t):
    humanoid("g", t, helmet="shuang_ling", cape="cloak", heavy=True)
    sword_waist("g", t, 0, 0, heavy=True)
    flag_waist("g", t, 0, 0)

def b_advisor_red(t):
    hh = humanoid("a", t, helmet="jinxian", robe=True, beard=True,
                  robe_color=t["cloth"])
    fan("a", t, hh[-1])
    tor("a_belt", (0, 0, Z0 + 0.52), 0.14, 0.018, t["white"])  # 玉带

def b_advisor_black(t):
    humanoid("a", t, helmet="wuguan", trophy=True)
    sword_waist("a", t, 0, 0)
    for lx in (-0.075, 0.075):  # 绑腿
        tor(f"a_wrap_{lx}", (lx, 0, Z0 + 0.18), 0.048, 0.012, t["cloth"])

def b_elephant_red(t):
    elephant("e", t, wild=False)

def b_elephant_black(t):
    elephant("e", t, wild=True)

def b_horse_red(t):
    bz = horse("h", t, 0, 0.05)
    hand = rider("h_rider", t, 0, 0.05, bz + 0.12, plume=t["lacquer"])
    spear("h", t, hand, s=0.75, tip=t["metal"])

def b_horse_black(t):
    bz = horse("h", t, 0, 0.05, armor_tone=t["armor2"], pouch=True)
    hand = rider("h_rider", t, 0, 0.05, bz + 0.12, plume=t["cloth"])
    spear("h", t, hand, s=0.75, tip=t["metal"])

def b_chariot_red(t):
    chariot("c", t, black=False)

def b_chariot_black(t):
    chariot("c", t, black=True)

def b_cannon_red(t):
    cannon_red("cn", t)

def b_cannon_black(t):
    trebuchet("cn", t)

def b_soldier_red(t):
    hh = humanoid("s", t, helmet="pibian")
    shield_round("s", t, hh[-1])
    dao("s", t, hh[1])
    for lx in (-0.075, 0.075):
        tor(f"s_wrap_{lx}", (lx, 0, Z0 + 0.18), 0.048, 0.012, t["cloth"])

def b_soldier_black(t):
    hh = humanoid("s", t, helmet="none", bun=True, trophy=True)
    shield_round("s", t, hh[-1], hide=True)
    dao("s", t, hh[1], short=True)

PIECES = [
    ("general_red", "red", "帅", b_general_red, 2.0),
    ("general_black", "black", "将", b_general_black, 2.0),
    ("advisor_red", "red", "仕", b_advisor_red, 2.0),
    ("advisor_black", "black", "士", b_advisor_black, 2.0),
    ("elephant_red", "red", "相", b_elephant_red, 2.4),
    ("elephant_black", "black", "象", b_elephant_black, 2.4),
    ("horse_red", "red", "马", b_horse_red, 2.2),
    ("horse_black", "black", "马", b_horse_black, 2.2),
    ("chariot_red", "red", "车", b_chariot_red, 2.3),
    ("chariot_black", "black", "车", b_chariot_black, 2.3),
    ("cannon_red", "red", "炮", b_cannon_red, 2.0),
    ("cannon_black", "black", "炮", b_cannon_black, 2.2),
    ("soldier_red", "red", "兵", b_soldier_red, 2.0),
    ("soldier_black", "black", "卒", b_soldier_black, 2.0),
]

# ---------------- 渲染 ----------------
def render_views(name, ortho):
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except Exception:
        scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 960
    world = bpy.data.worlds.new("studio")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.55, 0.55, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.35

    def area(nm, loc, energy):
        d = bpy.data.lights.new(nm, "AREA")
        d.energy = energy
        d.size = 3.0
        o = bpy.data.objects.new(nm, d)
        scene.collection.objects.link(o)
        o.location = loc
        o.rotation_euler = (Vector((0, -0.2, 0.8)) - o.location).to_track_quat("-Z", "Y").to_euler()

    area("key", (2.5, -2.5, 3.5), 320)
    area("fill", (-2.5, -1.5, 2.5), 180)
    area("rim", (0, 2.8, 3.0), 240)
    cd = bpy.data.cameras.new("cam")
    cd.type = "ORTHO"
    cd.ortho_scale = ortho
    cam = bpy.data.objects.new("cam", cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    for vn, loc in (("front", Vector((0, -4.6, 0.95))), ("side", Vector((4.6, -0.3, 0.95)))):
        cam.location = loc
        tgt = Vector((0, -0.2 if vn == "side" else 0, 0.95))
        cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(RENDER_DIR, f"{name}_{vn}.png")
        bpy.ops.render.render(write_still=True)

# ---------------- 主循环 ----------------
for name, camp, char, builder, ortho in PIECES:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    t = make_theme(camp)
    build_base(char, t)
    builder(t)
    blend_path = os.path.join(BLEND_DIR, f"{name}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(MODEL_DIR, f"{name}.glb"),
        export_format="GLB", export_yup=True, export_apply=True,
        export_animations=False, export_materials="EXPORT",
    )
    print("GLB-EXPORTED", name, flush=True)
    render_views(name, ortho)
    print("RENDERED", name, flush=True)

print("DONE-ALL-14")
