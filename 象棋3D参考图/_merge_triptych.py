# -*- coding: utf-8 -*-
"""把每个棋子的 正面/侧面/背面 三张正交视图横向合并为一张大图（供 Tripo 单图上传）"""
from pathlib import Path
from PIL import Image

ROOT = Path(r"C:\Users\guyu\cn_cheer\象棋3D参考图")
OUT = ROOT / "三视图合并"
OUT.mkdir(exist_ok=True)

PIECES = ["帅-红方", "将-黑方", "仕-红方", "士-黑方", "相-红方", "象-黑方",
          "马-红方", "马-黑方", "车-红方", "车-黑方", "炮-红方", "炮-黑方",
          "兵-红方", "卒-黑方"]

for name in PIECES:
    folder = ROOT / name
    imgs = []
    for view in ("正面", "侧面", "背面"):
        p = folder / f"{view}.png"
        if not p.exists():
            raise FileNotFoundError(p)
        imgs.append(Image.open(p).convert("RGB"))
    w, h = imgs[0].size
    assert all(im.size == (w, h) for im in imgs), name
    canvas = Image.new("RGB", (w * 3, h), (128, 128, 128))
    for i, im in enumerate(imgs):
        canvas.paste(im, (i * w, 0))
    out = OUT / f"{name}-三视图.png"
    canvas.save(out, optimize=True)
    print("OK", out, canvas.size)

print("DONE")
