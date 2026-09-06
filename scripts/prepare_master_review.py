"""Stage a textured source only after its full triangle surface passes comparison."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--geometry-report", required=True)
    args = parser.parse_args()
    source = Path(args.source).resolve()
    assert source.is_relative_to(ROOT / "assets/generated/meshy/general_red/texture")
    report = json.loads(Path(args.geometry_report).read_text(encoding="utf-8"))
    assert report["entire_triangle_surface_preserved"], "Do not stage a model that changed the source geometry"
    raw = (source / "model.glb").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == report["textured"]["sha256"]
    length = struct.unpack_from("<I", raw, 12)[0]
    doc = json.loads(raw[20:20 + length])
    binary = memoryview(raw)[28 + length:]
    images = []
    for item in doc.get("images", []):
        assert "bufferView" in item, "Expected embedded textures"
        view = doc["bufferViews"][item["bufferView"]]
        start = view.get("byteOffset", 0)
        with Image.open(io.BytesIO(binary[start:start+view["byteLength"]])) as image:
            images.append({"width":image.width,"height":image.height,"format":image.format})
    assert images and doc.get("materials")
    assert max(image["width"] for image in images) == 8192, "Expected actual 8K texture"
    assert any("normalTexture" in material and "metallicRoughnessTexture" in material.get("pbrMetallicRoughness",{}) for material in doc["materials"]), "Missing PBR channels"
    entry = {"file":"model.glb","bytes":len(raw),"triangles":report["textured"]["triangles"],
             "sha256":report["textured"]["sha256"],"images":images}
    output = ROOT / "public/assets/review/general_red/agent-master"
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "model.glb", output / "model.glb")
    manifest = {"piece":"general_red","source":"user-provided Meshy Agent GLB",
                "geometry_preserved":True,"user_approved":False,"variants":{"desktop":entry}}
    (output / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (source / "review-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False))


if __name__ == "__main__":
    main()
