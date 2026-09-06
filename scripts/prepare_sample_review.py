"""Validate and stage one local Blender export for review.html; no API calls.

Usage: python scripts/prepare_sample_review.py --source assets/generated/meshy/general_red/v1/review-r5
Requires Pillow for decoding the embedded texture headers.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import struct

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def inspect(path):
    raw = path.read_bytes()
    magic, version, size = struct.unpack_from("<4sII", raw)
    assert magic == b"glTF" and version == 2 and size == len(raw), "Invalid GLB header"
    json_size, kind = struct.unpack_from("<I4s", raw, 12)
    assert kind == b"JSON"
    document = json.loads(raw[20:20 + json_size])
    offset = 20 + json_size
    binary_size, kind = struct.unpack_from("<I4s", raw, offset)
    assert kind == b"BIN\x00"
    binary = raw[offset + 8:offset + 8 + binary_size]

    def values(index):
        accessor = document["accessors"][index]
        view = document["bufferViews"][accessor["bufferView"]]
        code = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}[accessor["componentType"]]
        count = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[accessor["type"]]
        pattern = "<" + code * count
        step = view.get("byteStride", struct.calcsize(pattern))
        start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        assert start + max(0, accessor["count"] - 1) * step + struct.calcsize(pattern) <= view.get("byteOffset", 0) + view["byteLength"]
        return [struct.unpack_from(pattern, binary, start + i * step) for i in range(accessor["count"])]

    triangles = 0
    primitive_counts = []
    for mesh in document["meshes"]:
        for primitive in mesh["primitives"]:
            assert primitive.get("mode", 4) == 4
            positions = values(primitive["attributes"]["POSITION"])
            indices = [row[0] for row in values(primitive["indices"])]
            assert len(indices) % 3 == 0 and min(indices) >= 0 and max(indices) < len(positions)
            assert all(math.isfinite(value) for row in positions for value in row)
            normals = values(primitive["attributes"]["NORMAL"])
            assert all(all(math.isfinite(value) for value in row) and 0.95 < sum(value * value for value in row) < 1.05 for row in normals)
            triangles += len(indices) // 3
            primitive_counts.append(len(indices) // 3)
    images = []
    for item in document.get("images", []):
        assert "uri" not in item, "Runtime textures must be embedded"
        view = document["bufferViews"][item["bufferView"]]
        start = view.get("byteOffset", 0)
        with Image.open(io.BytesIO(binary[start:start + view["byteLength"]])) as image:
            images.append({"name": item.get("name"), "width": image.width, "height": image.height, "format": image.format})
    assert len(images) == 3 and len(document["materials"]) == 3
    textured = [material for material in document["materials"] if "normalTexture" in material]
    assert len(textured) == 1 and "metallicRoughnessTexture" in textured[0]["pbrMetallicRoughness"]
    return {"file": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "triangles": triangles, "draw_primitives": len(primitive_counts), "primitive_triangles": primitive_counts,
            "materials": len(document["materials"]), "images": images}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    source = Path(args.source).resolve()
    assert source.is_relative_to(ROOT / "assets/generated/meshy/general_red"), "Expected a general_red candidate directory"
    output = ROOT / "public/assets/review/general_red"
    report = json.loads((source / "review.json").read_text(encoding="utf-8"))
    assert report["piece"] == "general_red" and not report["tool_test_only"]
    variants = {}
    for name, maximum, pixels in (("desktop", 20000, 4096), ("mobile", 20000, 2048), ("lod1", 8000, 2048), ("lod2", 3000, 2048)):
        item = inspect(source / f"general_red_{name}.glb")
        assert item["triangles"] <= maximum, f"{name} triangle budget exceeded"
        assert all(image["width"] == pixels and image["height"] == pixels for image in item["images"]), f"{name} texture size mismatch"
        variants[name] = item
    output.mkdir(parents=True, exist_ok=True)
    for item in variants.values():
        shutil.copy2(source / item["file"], output / item["file"])
    for view in ("front", "three_quarter", "back", "detail"):
        shutil.copy2(source / f"review_{view}.png", output / f"review_{view}.png")
    manifest = {"piece": "general_red", "review_revision": source.name, "user_approved": False,
                "consumed_credits": 35, "variants": variants}
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    (output / "manifest.json").write_text(text, encoding="utf-8")
    (source / "runtime-validation.json").write_text(text, encoding="utf-8")
    print(text)
    print("Local sample staged at public/assets/review/general_red. No source URLs or credentials included.")


if __name__ == "__main__":
    main()
