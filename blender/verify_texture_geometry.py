"""Compare original and textured GLB triangle surfaces, independent of UV seam splits.

Run with Blender's Python (NumPy bundled). No geometry is edited or exported.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import numpy as np


def surfaces(path):
    raw = path.read_bytes()
    assert struct.unpack_from("<4sII", raw) == (b"glTF", 2, len(raw))
    length, kind = struct.unpack_from("<I4s", raw, 12)
    assert kind == b"JSON"
    document = json.loads(raw[20:20 + length])
    binary_length, kind = struct.unpack_from("<I4s", raw, 20 + length)
    assert kind == b"BIN\x00"
    binary = memoryview(raw)[28 + length:28 + length + binary_length]

    def accessor(index):
        item = document["accessors"][index]
        assert "sparse" not in item
        view = document["bufferViews"][item["bufferView"]]
        dtype = np.dtype({5126:"<f4", 5125:"<u4", 5123:"<u2", 5121:"u1"}[item["componentType"]])
        width = {"SCALAR":1, "VEC2":2, "VEC3":3, "VEC4":4}[item["type"]]
        start = view.get("byteOffset", 0) + item.get("byteOffset", 0)
        step = view.get("byteStride", width * dtype.itemsize)
        assert start + max(0, item["count"] - 1) * step + width * dtype.itemsize <= view.get("byteOffset", 0) + view["byteLength"]
        return np.ndarray((item["count"], width), dtype=dtype, buffer=binary, offset=start, strides=(step,dtype.itemsize))

    def transform(node):
        if "matrix" in node:
            return np.array(node["matrix"], dtype=np.float64).reshape(4,4).T
        x,y,z,w = node.get("rotation", [0,0,0,1])
        matrix = np.eye(4)
        matrix[:3,:3] = np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                                  [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                                  [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]) @ np.diag(node.get("scale", [1,1,1]))
        matrix[:3,3] = node.get("translation", [0,0,0])
        return matrix

    parts = []
    def visit(index, parent):
        node = document["nodes"][index]
        world = parent @ transform(node)
        if "mesh" in node:
            for primitive in document["meshes"][node["mesh"]]["primitives"]:
                assert primitive.get("mode",4) == 4
                positions = accessor(primitive["attributes"]["POSITION"])
                points = positions @ world[:3,:3].T + world[:3,3]
                assert np.isfinite(points).all()
                indices = accessor(primitive["indices"]).ravel() if "indices" in primitive else np.arange(len(points))
                assert len(indices) % 3 == 0 and indices.max() < len(points)
                parts.append(points[indices].reshape(-1,3,3).astype(np.float32))
        for child in node.get("children", []):
            visit(child, world)
    for node in document["scenes"][document.get("scene",0)]["nodes"]:
        visit(node, np.eye(4))
    triangles = np.concatenate(parts)
    summary = {"file":str(path), "sha256":hashlib.sha256(raw).hexdigest(), "triangles":len(triangles),
               "bounds_min":triangles.min(axis=(0,1)).tolist(), "bounds_max":triangles.max(axis=(0,1)).tolist(),
               "materials":len(document.get("materials",[])), "textures":len(document.get("textures",[]))}
    return triangles, summary


def signatures(triangles, precision=1e-6):
    integers = (np.ascontiguousarray(triangles.astype("<f4")).view("<u4") if precision is None
                else np.rint(triangles.astype(np.float64) / precision).astype(np.int32))
    order = np.lexsort((integers[:,:,2],integers[:,:,1],integers[:,:,0]), axis=1)
    canonical = np.take_along_axis(integers, order[:,:,None], axis=1)
    records = np.ascontiguousarray(canonical.reshape(-1,9)).view(np.dtype((np.void,36))).ravel()
    records.sort()
    return records


def main():
    args_in = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--textured", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(args_in)
    source, source_info = surfaces(Path(args.source).resolve())
    target, target_info = surfaces(Path(args.textured).resolve())
    source_signatures = signatures(source, precision=None)
    target_signatures = signatures(target, precision=None)
    identical = np.array_equal(source_signatures, target_signatures)
    report = {"source":source_info, "textured":target_info, "precision":0,
              "comparison":"bit-exact float32 world-space triangles, vertex and face order ignored; UV seam splits allowed",
              "entire_triangle_surface_preserved":bool(identical), "visual_review_required":True,
              "source_file_modified":False}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if not identical:
        raise RuntimeError("Textured output differs from source geometry; do not promote without further review")


if __name__ == "__main__":
    main()
