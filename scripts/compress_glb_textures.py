"""Encode GLB texture images as UASTC KTX2 with mips; geometry bytes stay exact."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--max-size", type=int, choices=(1024, 2048, 4096))
    parser.add_argument("--reuse-pair", nargs=2, metavar=('WEBP_GLB','KTX_GLB'), help='Reuse verified identical source image bytes from an earlier local export')
    args = parser.parse_args()
    source, output = Path(args.input).resolve(), Path(args.output).resolve()
    assert source != output and not output.exists()
    raw = source.read_bytes()
    length = struct.unpack_from("<I", raw, 12)[0]
    doc = json.loads(raw[20:20+length])
    binary = memoryview(raw)[28+length:]
    colors, normals = set(), set()
    for material in doc.get("materials", []):
        pbr = material.get("pbrMetallicRoughness", {})
        for info in (pbr.get("baseColorTexture"), material.get("emissiveTexture")):
            if info:
                colors.add(info["index"])
        if material.get("normalTexture"):
            normals.add(material["normalTexture"]["index"])
    def image_index(texture):
        return texture.get("source", texture.get("extensions", {}).get("EXT_texture_webp", {}).get("source"))
    color_images = {image_index(doc["textures"][i]) for i in colors}
    normal_images = {image_index(doc["textures"][i]) for i in normals}
    reused={}
    if args.reuse_pair and not args.max_size:
        pair=[]
        for name in args.reuse_pair:
            data=Path(name).read_bytes();n=struct.unpack_from('<I',data,12)[0];pair.append((json.loads(data[20:20+n]),data[28+n:]))
        old_doc,old_binary=pair[0];old_ktx,ktx_binary=pair[1]
        assert len(old_doc['images'])==len(old_ktx['images'])
        for image,compressed in zip(old_doc['images'],old_ktx['images']):
            view=old_doc['bufferViews'][image['bufferView']];packed=old_ktx['bufferViews'][compressed['bufferView']]
            encoded_image=ktx_binary[packed.get('byteOffset',0):packed.get('byteOffset',0)+packed['byteLength']]
            assert compressed['mimeType']=='image/ktx2'
            digest=hashlib.sha256(old_binary[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']]).hexdigest()
            reused[digest]=encoded_image
    replacements, image_reports = {}, []
    ktx = ROOT / ".meshy/ktx/bin/toktx.exe"
    validator = ROOT / ".meshy/ktx/bin/ktx.exe"
    with tempfile.TemporaryDirectory(prefix="ktx-", dir=ROOT / ".meshy") as temporary:
        temp = Path(temporary)
        for index, image in enumerate(doc.get("images", [])):
            view = doc["bufferViews"][image["bufferView"]]
            start = view.get("byteOffset", 0)
            original = bytes(binary[start:start+view["byteLength"]])
            pixels = Image.open(io.BytesIO(original)).convert("RGB")
            if args.max_size and max(pixels.size) > args.max_size:
                pixels.thumbnail((args.max_size, args.max_size), Image.Resampling.LANCZOS)
            png, encoded = temp / f"image{index}.png", temp / f"image{index}.ktx2"
            pixels.save(png)
            transfer = "srgb" if index in color_images else "linear"
            # Keep XYZ normals: --normal_mode would store XY in RA and require
            # a different runtime shader. These textures use standard glTF normals.
            command = [str(ktx), "--t2", "--encode", "uastc", "--uastc_quality", "2",
                       "--uastc_rdo_l", "0.75", "--uastc_rdo_m", "--zcmp", "18", "--genmipmap",
                       "--assign_oetf", transfer, "--assign_primaries", "bt709" if transfer == "srgb" else "none",
                       "--threads", str(args.threads), str(encoded), str(png)]
            cached=reused.get(hashlib.sha256(original).hexdigest())
            if cached:encoded.write_bytes(cached)
            else:subprocess.run(command, check=True, capture_output=True)
            checked = subprocess.run([str(validator), "validate", "--gltf-basisu", str(encoded)], capture_output=True)
            if checked.returncode:
                raise RuntimeError((checked.stdout + checked.stderr).decode("utf-8", errors="replace"))
            data = encoded.read_bytes()
            assert data[:12] == b"\xabKTX 20\xbb\r\n\x1a\n"
            width, height, levels = struct.unpack_from("<I", data, 20)[0], struct.unpack_from("<I", data, 24)[0], struct.unpack_from("<I", data, 40)[0]
            assert (width, height) == pixels.size and levels > 1
            replacements[image["bufferView"]] = data
            image["mimeType"] = "image/ktx2"
            image_reports.append({"index": index, "size": [width, height], "mips": levels,
                                  "reused_identical_source_bytes":bool(cached),
                                  "transfer": transfer, "normal_xyz": index in normal_images,
                                  "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            print("KTX2", source.stem, index, width, height, levels, len(data), flush=True)
    chunks, size = [], 0
    for index, view in enumerate(doc["bufferViews"]):
        start = view.get("byteOffset", 0)
        data = replacements.get(index, bytes(binary[start:start+view["byteLength"]]))
        view.update(byteOffset=size, byteLength=len(data))
        padded = data + b"\0" * (-len(data) % 4)
        chunks.append(padded)
        size += len(padded)
    for texture in doc["textures"]:
        index = image_index(texture)
        texture.pop("source", None)
        extensions = texture.setdefault("extensions", {})
        extensions.pop("EXT_texture_webp", None)
        extensions["KHR_texture_basisu"] = {"source": index}
    for key in ("extensionsUsed", "extensionsRequired"):
        doc[key] = [value for value in doc.get(key, []) if value != "EXT_texture_webp"]
        if "KHR_texture_basisu" not in doc[key]:
            doc[key].append("KHR_texture_basisu")
    doc["buffers"] = [{"byteLength": size}]
    encoded = json.dumps(doc, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 4)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(struct.pack("<4sII", b"glTF", 2, 28+len(encoded)+size))
        handle.write(struct.pack("<I4s", len(encoded), b"JSON") + encoded)
        handle.write(struct.pack("<I4s", size, b"BIN\0"))
        for chunk in chunks:
            handle.write(chunk)
    report = {"source": str(source), "source_sha256": hashlib.sha256(raw).hexdigest(),
              "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "bytes": output.stat().st_size,
              "encoding": "UASTC quality 2, RDO .75, Zstd 18, full mipmaps", "ktx_version": "4.4.2",
              "geometry_buffer_views_unchanged": True, "images": image_reports, "source_unchanged": True}
    output.with_suffix(".ktx.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
