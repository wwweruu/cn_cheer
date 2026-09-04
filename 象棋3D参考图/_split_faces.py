# -*- coding: utf-8 -*-
"""人脸拆分：每枚棋子生成
1) 人脸三视图（正/侧/背头部裁剪，各 512×512 拼成 1536×512）
2) 无脸身体图（正面/侧面脸部以肤色椭圆柔边抹空，背面无人脸不处理）
不修改原始文件。坐标为面板内相对值 (x0,y0,x1,y1)，面板 1024×1536。
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(r"C:\Users\guyu\cn_cheer\象棋3D参考图")
FACE_OUT = ROOT / "人脸三视图"
BLANK_OUT = ROOT / "无脸身体三视图"
FACE_OUT.mkdir(exist_ok=True)
BLANK_OUT.mkdir(exist_ok=True)
PANEL_W, PANEL_H = 1024, 1536

# head_*：头部裁剪框（含盔冠，供人脸三视图）；face_*：脸部抹空框（仅正/侧面）
DATA = {
    "帅-红方": dict(head_f=(.37,.00,.63,.21), head_s=(.38,.00,.60,.19), head_b=(.40,.00,.60,.19),
                    face_f=(.452,.115,.548,.185), face_s=(.435,.09,.50,.155)),
    "将-黑方": dict(head_f=(.40,.00,.62,.18), head_s=(.40,.00,.62,.18), head_b=(.40,.00,.62,.18),
                    face_f=(.46,.095,.545,.165), face_s=(.445,.09,.505,.16)),
    "仕-红方": dict(head_f=(.42,.01,.58,.15), head_s=(.41,.01,.58,.15), head_b=(.42,.01,.58,.15),
                    face_f=(.455,.075,.545,.135), face_s=(.445,.07,.50,.125)),
    "士-黑方": dict(head_f=(.42,.01,.58,.13), head_s=(.42,.01,.58,.13), head_b=(.42,.01,.58,.13),
                    face_f=(.46,.055,.54,.115), face_s=(.45,.05,.505,.11)),
    "相-红方": dict(head_f=(.42,.05,.56,.16), head_s=(.45,.08,.57,.18), head_b=(.44,.07,.58,.18),
                    face_f=(.465,.095,.515,.125), face_s=(.475,.115,.52,.15)),
    "象-黑方": dict(head_f=(.11,.02,.22,.11), head_s=(.44,.05,.53,.13), head_b=(.76,.01,.88,.10),
                    face_f=(.145,.055,.175,.09), face_s=(.46,.085,.49,.11)),
    "马-红方": dict(head_f=(.40,.01,.58,.12), head_s=(.44,.04,.58,.15), head_b=(.42,.00,.60,.11),
                    face_f=(.455,.055,.535,.105), face_s=(.475,.095,.525,.135)),
    "马-黑方": dict(head_f=(.42,.01,.58,.12), head_s=(.44,.05,.58,.15), head_b=(.42,.00,.60,.11),
                    face_f=(.455,.05,.535,.095), face_s=(.47,.10,.52,.135)),
    "车-红方": dict(head_f=(.43,.16,.54,.26), head_s=(.39,.27,.50,.37), head_b=(.36,.15,.46,.25),
                    face_f=(.465,.20,.50,.235), face_s=(.435,.315,.465,.345)),
    "车-黑方": dict(head_f=(.44,.16,.55,.25), head_s=(.49,.28,.58,.37), head_b=(.45,.16,.55,.24),
                    face_f=(.475,.195,.51,.23), face_s=(.53,.32,.555,.35)),
    "炮-红方": dict(head_f=(.20,.04,.31,.16), head_s=(.12,.14,.22,.26), head_b=(.68,.03,.79,.15),
                    face_f=(.235,.105,.275,.145), face_s=(.16,.21,.185,.245)),
    "炮-黑方": dict(head_f=(.12,.44,.22,.53), head_s=(.10,.45,.21,.55), head_b=(.74,.44,.85,.54),
                    face_f=(.148,.47,.185,.51), face_s=(.15,.50,.175,.535)),
    "兵-红方": dict(head_f=(.42,.01,.56,.12), head_s=(.37,.02,.48,.13), head_b=(.45,.01,.56,.11),
                    face_f=(.455,.055,.525,.105), face_s=(.40,.075,.445,.12)),
    "卒-黑方": dict(head_f=(.44,.01,.58,.11), head_s=(.47,.01,.58,.12), head_b=(.48,.01,.60,.11),
                    face_f=(.475,.05,.54,.10), face_s=(.515,.065,.555,.11)),
}

SKIN = (198, 158, 130)  # 空白脸填充色

def px(box):
    x0, y0, x1, y1 = box
    return (int(x0 * PANEL_W), int(y0 * PANEL_H), int(x1 * PANEL_W), int(y1 * PANEL_H))

def crop_square(img, box):
    x0, y0, x1, y1 = px(box)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width, x1), min(img.height, y1)
    w, h = x1 - x0, y1 - y0
    side = max(w, h)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    nx0, ny0 = max(0, cx - side // 2), max(0, cy - side // 2)
    nx1, ny1 = min(img.width, nx0 + side), min(img.height, ny0 + side)
    return img.crop((nx0, ny0, nx1, ny1)).resize((512, 512), Image.LANCZOS)

def blank_face(img, box):
    x0, y0, x1, y1 = px(box)
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((x0, y0, x1, y1), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(6))
    patch = Image.new("RGB", img.size, SKIN)
    return Image.composite(patch, img, mask)

for name, d in DATA.items():
    folder = ROOT / name
    views = {v: Image.open(folder / f"{v}.png").convert("RGB") for v in ("正面", "侧面", "背面")}

    # 1) 人脸三视图
    cells = [crop_square(views["正面"], d["head_f"]),
             crop_square(views["侧面"], d["head_s"]),
             crop_square(views["背面"], d["head_b"])]
    tri = Image.new("RGB", (1536, 512), (128, 128, 128))
    for i, c in enumerate(cells):
        tri.paste(c, (i * 512, 0))
    tri.save(FACE_OUT / f"{name}-人脸三视图.png", optimize=True)

    # 2) 无脸身体（正面+侧面抹脸，背面原样），输出单视图与合并图
    blanked = {}
    for vn, key in (("正面", "face_f"), ("侧面", "face_s")):
        blanked[vn] = blank_face(views[vn], d[key])
        blanked[vn].save(BLANK_OUT / f"{name}-{vn}-无脸.png", optimize=True)
    views["背面"].save(BLANK_OUT / f"{name}-背面.png", optimize=True)
    merged = Image.new("RGB", (PANEL_W * 3, PANEL_H), (128, 128, 128))
    for i, vn in enumerate(("正面", "侧面", "背面")):
        merged.paste(blanked.get(vn, views[vn]), (i * PANEL_W, 0))
    merged.save(BLANK_OUT / f"{name}-三视图-无脸.png", optimize=True)
    print("OK", name)

print("DONE")
