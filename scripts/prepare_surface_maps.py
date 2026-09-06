"""Finish approved UV swatches for seamless repeated use; retain native originals."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageFilter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".meshy/pydeps"))
from scipy.fft import rfft2, irfft2


def periodic(array):
    """Remove the smooth boundary mismatch component, keeping fine surface detail."""
    h, w = array.shape[:2]
    denom = 2 * (np.cos(2*np.pi*np.arange(h)/h)[:, None] + np.cos(2*np.pi*np.arange(w//2+1)/w)[None, :] - 2)
    denom[0, 0] = 1
    result = array.astype(np.float32).copy()
    for channel in range(array.shape[2]):
        a = array[:, :, channel].astype(np.float32)
        boundary = np.zeros((h, w), np.float32)
        boundary[0] = a[-1] - a[0]
        boundary[-1] = a[0] - a[-1]
        boundary[:, 0] += a[:, -1] - a[:, 0]
        boundary[:, -1] += a[:, 0] - a[:, -1]
        spectrum = rfft2(boundary) / denom
        spectrum[0, 0] = 0
        result[:, :, channel] -= irfft2(spectrum, s=(h, w)).astype(np.float32)
    return result


def seams(a):
    a = a.astype(float)
    return {"left_right": float(np.abs(a[:, 0] - a[:, -1]).mean()),
            "top_bottom": float(np.abs(a[0] - a[-1]).mean())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", required=True)
    parser.add_argument("--repair-dirt-spot", action="store_true")
    args = parser.parse_args()
    base = ROOT / "assets/generated/meshy/scene" / args.asset / "surface/v1"
    output = base / "finished"
    assert not output.exists()
    output.mkdir()
    report = {"asset": args.asset, "originals_unchanged": True,
              "processing": "Local periodic boundary correction; no resolution enlargement", "images": {}}
    for channel in ("base_color", "normal", "roughness", "metallic"):
        path = base / f"texture_0_{channel}.png"
        image = Image.open(path).convert("RGB")
        original = np.array(image)
        if args.repair_dirt_spot:
            # A conspicuous orange speck repeats as a grid. Copy nearby matching
            # swatch material using the same UV-space mask in every PBR channel.
            w, h = image.size
            cx, cy, radius = round(w*.741), round(h*.426), round(min(w,h)*.025)
            patch = image.crop((cx-radius-round(w*.09), cy-radius, cx+radius-round(w*.09), cy+radius))
            mask = Image.new("L", patch.size, 0)
            from PIL import ImageDraw
            ImageDraw.Draw(mask).ellipse((radius*.25, radius*.25, radius*1.75, radius*1.75), fill=255)
            mask = mask.filter(ImageFilter.GaussianBlur(radius*.22))
            image.paste(patch, (cx-radius, cy-radius), mask)
        pixels = periodic(np.array(image))
        if channel == "normal":
            vectors = pixels/127.5 - 1
            vectors /= np.maximum(np.linalg.norm(vectors, axis=2, keepdims=True), 1e-8)
            pixels = (vectors+1)*127.5
        pixels = np.clip(np.rint(pixels), 0, 255).astype(np.uint8)
        final = Image.fromarray(pixels)
        if channel in ("roughness", "metallic"):
            final = final.convert("L")
        final.save(output / f"{channel}.png")
        report["images"][channel] = {"size": list(image.size), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256((output/f"{channel}.png").read_bytes()).hexdigest(),
            "before_seam_mae": seams(original), "after_seam_mae": seams(pixels)}
    rough = Image.open(output / "roughness.png")
    metal = Image.open(output / "metallic.png")
    assert rough.size == metal.size
    Image.merge("RGB", (Image.new("L", rough.size, 255), rough, metal)).save(output / "orm.png")
    tile = Image.open(output / "base_color.png").resize((450, 450), Image.Resampling.LANCZOS)
    sheet = Image.new("RGB", (1350, 1350))
    for y in range(3):
        for x in range(3):
            sheet.paste(tile, (x*450, y*450))
    sheet.save(output / "tile-check.png")
    (output/"surface.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
