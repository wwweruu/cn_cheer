"""Close the exposed edge of a local pedestal infill, keeping original files intact.

Applies the same explicit finishing geometry to clay and textured assets so the
final geometry can still be checked independently. No voxelization or remeshing.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct

from restore_source_geometry import GLB, np, cKDTree


def write_mesh(path, reference, positions, indices, attributes):
    doc = {"asset": {"version": "2.0", "generator": "cn-chess pedestal edge finishing"},
           "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
           "meshes": [], "bufferViews": [], "accessors": [], "buffers": []}
    chunks, size = [], 0
    def view(data, target=None):
        nonlocal size
        raw = bytes(data)
        item = {"buffer": 0, "byteOffset": size, "byteLength": len(raw)}
        if target:
            item["target"] = target
        doc["bufferViews"].append(item)
        padded = raw + b"\0" * (-len(raw) % 4)
        chunks.append(padded)
        size += len(padded)
        return len(doc["bufferViews"]) - 1
    def accessor(array, kind, component, target):
        item = {"bufferView": view(array.tobytes(), target), "componentType": component,
                "count": len(array), "type": kind}
        if kind == "VEC3":
            item.update(min=array.min(axis=0).tolist(), max=array.max(axis=0).tolist())
        doc["accessors"].append(item)
        return len(doc["accessors"]) - 1
    attrs = {"POSITION": accessor(positions.astype("<f4"), "VEC3", 5126, 34962)}
    for name, array in attributes.items():
        attrs[name] = accessor(array.astype("<f4"), "VEC2" if name == "TEXCOORD_0" else "VEC3", 5126, 34962)
    primitive = {"attributes": attrs, "indices": accessor(indices.reshape(-1).astype("<u4"), "SCALAR", 5125, 34963), "mode": 4}
    if "material" in reference.primitive:
        primitive["material"] = reference.primitive["material"]
    doc["meshes"] = [{"primitives": [primitive]}]
    for key in ("materials", "textures", "samplers", "extensionsUsed", "extensionsRequired"):
        if key in reference.doc:
            doc[key] = copy.deepcopy(reference.doc[key])
    if "images" in reference.doc:
        doc["images"] = []
        for image in reference.doc["images"]:
            old = reference.doc["bufferViews"][image["bufferView"]]
            start = old.get("byteOffset", 0)
            doc["images"].append({**image, "bufferView": view(reference.binary[start:start + old["byteLength"]])})
    doc["buffers"] = [{"byteLength": size}]
    raw = json.dumps(doc, separators=(",", ":")).encode()
    raw += b" " * (-len(raw) % 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(struct.pack("<4sII", b"glTF", 2, 28 + len(raw) + size))
        output.write(struct.pack("<I4s", len(raw), b"JSON") + raw)
        output.write(struct.pack("<I4s", size, b"BIN\0"))
        for chunk in chunks:
            output.write(chunk)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--textured")
    parser.add_argument("--output-source", required=True)
    parser.add_argument("--output-textured")
    parser.add_argument("--thickness", type=float, default=.035)
    parser.add_argument("--raise-cap", type=float, default=0)
    args = parser.parse_args()
    source = GLB(Path(args.source))
    sp, si = source.attribute("POSITION"), source.triangles()
    # These locally assembled sources explicitly append a 256-triangle fan.
    cap_ids = np.unique(si[-256:])
    assert len(cap_ids) == 257
    cap = sp[cap_ids].copy()
    assert float(np.ptp(cap[:, 1])) < 1e-7
    ring = cap[1:].copy()
    ring[:, 1] += args.raise_cap
    lower = ring.copy()
    lower[:, 1] -= args.thickness
    band = np.concatenate([ring, lower])
    band_indices = np.array([[i, (i+1) % 256, 256+i] for i in range(256)] +
                            [[(i+1) % 256, 256+(i+1) % 256, 256+i] for i in range(256)], dtype="<u4")
    targets = [(source, Path(args.output_source))]
    if args.textured:
        assert args.output_textured
        targets.append((GLB(Path(args.textured)), Path(args.output_textured)))
    for target, output in targets:
        p = target.attribute("POSITION").copy()
        attrs = {}
        if args.raise_cap:
            distance, _ = cKDTree(cap).query(p, workers=4)
            p[distance < 1e-8, 1] += args.raise_cap
        if "TEXCOORD_0" in target.primitive["attributes"]:
            d, nearest = cKDTree(target.attribute("POSITION")).query(cap[1:], workers=4)
            assert float(d.max()) < 1e-8
            uv = target.attribute("TEXCOORD_0")[nearest]
            attrs["TEXCOORD_0"] = np.concatenate([target.attribute("TEXCOORD_0"), uv, uv])
            normals = band - np.array([cap[0, 0], 0, cap[0, 2]])
            normals[:, 1] = 0
            normals /= np.linalg.norm(normals, axis=1)[:, None]
            attrs["NORMAL"] = np.concatenate([target.attribute("NORMAL"), normals])
        write_mesh(output, target, np.concatenate([p, band]),
                   np.concatenate([target.triangles(), band_indices + len(p)]), attrs)
        report = {"source": str(target.path), "source_sha256": hashlib.sha256(target.raw).hexdigest(),
                  "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                  "added_band_triangles": 512, "thickness": args.thickness,
                  "raised_cap": args.raise_cap, "original_files_unchanged": True,
                  "source_triangles_retained": len(target.triangles()), "requires_visual_review": True}
        output.with_suffix(".finish.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(output.name, report["output_sha256"], flush=True)


if __name__ == "__main__":
    main()
