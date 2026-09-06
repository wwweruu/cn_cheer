"""Transfer Meshy UV/PBR onto the exact original triangles after uniform normalization.

Requires NumPy and SciPy (optionally installed under .meshy/pydeps). Refuses a
substantially changed surface. Source coordinates/faces and source file stay intact.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".meshy/pydeps"))
import numpy as np
from scipy.spatial import cKDTree


class GLB:
    def __init__(self, path):
        self.path = path.resolve()
        self.raw = self.path.read_bytes()
        assert struct.unpack_from("<4sII", self.raw) == (b"glTF",2,len(self.raw))
        length = struct.unpack_from("<I", self.raw,12)[0]
        self.doc = json.loads(self.raw[20:20+length])
        self.binary = memoryview(self.raw)[28+length:]
        assert len(self.doc["meshes"]) == 1 and len(self.doc["meshes"][0]["primitives"]) == 1
        assert len(self.doc["nodes"]) == 1
        node = self.doc["nodes"][0]
        assert not any(key in node for key in ("translation","rotation","scale"))
        assert np.array_equal(np.array(node.get("matrix",np.eye(4).ravel())).reshape(4,4),np.eye(4))
        self.primitive = self.doc["meshes"][0]["primitives"][0]

    def accessor(self,index):
        item = self.doc["accessors"][index]
        view = self.doc["bufferViews"][item["bufferView"]]
        dtype = np.dtype({5126:"<f4",5125:"<u4",5123:"<u2"}[item["componentType"]])
        width = {"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4}[item["type"]]
        start = view.get("byteOffset",0)+item.get("byteOffset",0)
        return np.ndarray((item["count"],width),dtype=dtype,buffer=self.binary,offset=start,
                          strides=(view.get("byteStride",dtype.itemsize*width),dtype.itemsize))

    def attribute(self,name):
        return self.accessor(self.primitive["attributes"][name])

    def triangles(self):
        return self.accessor(self.primitive["indices"]).reshape(-1,3)


def face_keys(ids):
    return np.ascontiguousarray(np.sort(ids,axis=1).astype("<u4")).view(np.dtype((np.void,12))).ravel()


def closest_triangle_weights(point, triangles):
    """Closest points on a small candidate set, including edges and degenerate faces."""
    a, b, c = (triangles[:, i].astype(np.float64) for i in range(3))
    ab, ac, ap = b-a, c-a, point-a
    dot = lambda x, y: np.einsum("ij,ij->i", x, y)
    d00, d01, d11 = dot(ab, ab), dot(ab, ac), dot(ac, ac)
    d20, d21 = dot(ap, ab), dot(ap, ac)
    denominator = d00*d11-d01*d01
    safe = np.where(np.abs(denominator) > 1e-24, denominator, 1)
    v, w = (d11*d20-d01*d21)/safe, (d00*d21-d01*d20)/safe
    face = np.column_stack((1-v-w, v, w))
    valid = (face.min(axis=1) >= 0) & (np.abs(denominator) > 1e-24)
    candidates = [face]
    for start, end in ((0,1), (1,2), (2,0)):
        edge = triangles[:,end]-triangles[:,start]
        length2 = dot(edge, edge)
        t = np.clip(dot(point-triangles[:,start], edge)/np.maximum(length2, 1e-30), 0, 1)
        weights = np.zeros_like(face)
        weights[:,start], weights[:,end] = 1-t, t
        candidates.append(weights)
    weights = np.stack(candidates, axis=1)
    projected = np.einsum("nki,nij->nkj", weights, triangles)
    distances = np.linalg.norm(projected-point, axis=2)
    distances[~valid,0] = np.inf
    tri, candidate = np.unravel_index(distances.argmin(), distances.shape)
    return tri, weights[tri,candidate], float(distances[tri,candidate])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source",required=True)
    parser.add_argument("--textured",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--reviewed-area-limit", type=float, default=0.00001,
                        help="After auditing missing-face positions; geometry and UV-distance checks stay strict")
    args = parser.parse_args()
    assert 0 < args.reviewed_area_limit <= 0.00002
    source, target = GLB(Path(args.source)), GLB(Path(args.textured))
    output = Path(args.output).resolve()
    assert output not in {source.path,target.path}
    sp, tp = source.attribute("POSITION"), target.attribute("POSITION")
    si, ti = source.triangles(), target.triangles()
    low, high = sp.min(axis=0), sp.max(axis=0)
    # Meshy normalizes the longest dimension; wide/deep compound pieces are
    # not necessarily tallest along Y (confirmed on the black elephant).
    scale = 2.0 / float(np.max(high-low))
    center = (low.astype(np.float64)+high)/2
    unique_source, source_ids = np.unique(sp,axis=0,return_inverse=True)
    normalized = (unique_source.astype(np.float64)-center)*scale
    distances, target_ids = cKDTree(normalized).query(tp,k=1,workers=4)
    error = float(distances.max())
    print(f"Mapped texture vertices to original geometry; max normalized error {error:.9f}",flush=True)
    assert error < 0.00001, "Textured vertices moved beyond normalization rounding"
    source_faces, target_faces = source_ids[si], target_ids[ti]
    source_keys, target_keys = face_keys(source_faces), face_keys(target_faces)
    order = np.argsort(target_keys)
    sorted_keys = target_keys[order]
    offsets = np.searchsorted(sorted_keys,source_keys)
    in_range = offsets < len(order)
    matched = in_range.copy()
    matched[in_range] &= sorted_keys[offsets[in_range]] == source_keys[in_range]
    missing = np.flatnonzero(~matched)
    print(f"Exact face correspondences: {int(matched.sum())}/{len(si)}; unmatched original faces {len(missing)}",flush=True)
    assert len(missing) <= max(512,len(si)*0.0002), "Too many source faces changed; review instead of transferring"
    missing_area_max = 0.0
    if len(missing):
        positions = sp[si[missing]].astype(np.float64)
        areas = np.linalg.norm(np.cross(positions[:,1]-positions[:,0],positions[:,2]-positions[:,0]),axis=1)*0.5
        missing_area_max = float(areas.max())
        print(f"Largest unmatched original triangle area: {missing_area_max:.12g}",flush=True)
        assert missing_area_max < args.reviewed_area_limit, "A meaningful original surface changed"

    # Map each original corner to the corresponding textured face corner; this preserves UV seams.
    target_vertex = np.empty((len(si),3),dtype=np.uint32)
    selected_faces = order[offsets[matched]]
    selected_ids = target_faces[selected_faces]
    selected_indices = ti[selected_faces]
    for corner in range(3):
        matches = selected_ids == source_faces[matched,corner,None]
        assert matches.any(axis=1).all()
        target_vertex[matched,corner] = selected_indices[np.arange(len(selected_faces)),matches.argmax(axis=1)]
    if len(missing):
        # Meshy removed tiny/degenerate triangles. Restore every one, sourcing UVs from coincident nearby corners.
        points = (sp[si[missing]].reshape(-1,3).astype(np.float64)-center)*scale
        nearby_error, nearby = cKDTree(tp).query(points,k=1,workers=4)
        print(f"Restored-face texture projection distance: max {float(nearby_error.max()):.9f}, p95 {float(np.percentile(nearby_error,95)):.9f}",flush=True)
        # UV lookup may move up to 0.1% of normalized height on these tiny restored
        # faces only. Their actual geometry below still uses the exact source points.
        target_vertex[missing] = nearby.reshape(-1,3)
    uv = target.attribute("TEXCOORD_0")[target_vertex].reshape(-1,2).astype("<f4")
    normals = target.attribute("NORMAL")[target_vertex].reshape(-1,3).astype("<f4")
    projected_corner_count = 0
    if len(missing) and float(nearby_error.max()) >= 0.002:
        # A nearby triangle interior can be much closer than any vertex.
        # Interpolate only the exceptional restored corners; preserve the same
        # surface-distance guard and all original geometry and texture bytes.
        centroids = tp[ti].mean(axis=1)
        tree = cKDTree(centroids)
        for corner in np.flatnonzero(nearby_error >= 0.002):
            _, candidates = tree.query(points[corner], k=32)
            local, weights, distance = closest_triangle_weights(points[corner], tp[ti[candidates]])
            assert distance < 0.002, "Restored corner is not close to the textured surface"
            indices = ti[candidates[local]]
            output_corner = missing[corner//3]*3 + corner%3
            uv[output_corner] = weights @ target.attribute("TEXCOORD_0")[indices]
            normal = weights @ target.attribute("NORMAL")[indices]
            normals[output_corner] = normal / max(np.linalg.norm(normal), 1e-20)
            nearby_error[corner] = distance
            projected_corner_count += 1
            print("Interpolated restored corner", points[corner].tolist(), "surface distance", distance, flush=True)
        del centroids, tree
    assert not len(missing) or float(nearby_error.max()) < 0.002
    records = np.empty((len(si)*3,6),dtype="<u4")
    records[:,0] = source_faces.ravel()
    records[:,1:3] = uv.view("<u4")
    records[:,3:6] = normals.view("<u4")
    print("Packing exact source positions with transferred UV seams and normals",flush=True)
    _, first, indices = np.unique(records.view(np.dtype((np.void,24))).ravel(),return_index=True,return_inverse=True)
    positions = unique_source[records[first,0]].astype("<f4")
    texcoords, vertex_normals = uv[first], normals[first]
    indices = indices.astype("<u4")
    doc = {"asset":{"version":"2.0","generator":"cn-chess exact-source geometry + Meshy PBR transfer"},
           "scene":0,"scenes":[{"nodes":[0]}],"nodes":[{"mesh":0}],"meshes":[],
           "bufferViews":[],"accessors":[],"buffers":[]}
    for key in ("materials","textures","samplers","extensionsUsed","extensionsRequired"):
        if key in target.doc:
            doc[key] = copy.deepcopy(target.doc[key])
    chunks, size = [],0
    def view(data, target_type=None):
        nonlocal size
        raw = bytes(data)
        item = {"buffer":0,"byteOffset":size,"byteLength":len(raw)}
        if target_type:
            item["target"] = target_type
        doc["bufferViews"].append(item)
        padded = raw + b"\0"*((-len(raw))%4)
        chunks.append(padded)
        size += len(padded)
        return len(doc["bufferViews"])-1
    def accessor(array,kind,component,target_type):
        item = {"bufferView":view(array.tobytes(),target_type),"componentType":component,"count":len(array),"type":kind}
        if kind == "VEC3":
            item.update(min=array.min(axis=0).tolist(),max=array.max(axis=0).tolist())
        doc["accessors"].append(item)
        return len(doc["accessors"])-1
    attrs = {"POSITION":accessor(positions,"VEC3",5126,34962),"NORMAL":accessor(vertex_normals,"VEC3",5126,34962),
             "TEXCOORD_0":accessor(texcoords,"VEC2",5126,34962)}
    index_accessor = accessor(indices,"SCALAR",5125,34963)
    doc["meshes"] = [{"primitives":[{"attributes":attrs,"indices":index_accessor,"material":target.primitive.get("material",0),"mode":4}]}]
    doc["images"] = []
    for image in target.doc["images"]:
        old_view = target.doc["bufferViews"][image["bufferView"]]
        start = old_view.get("byteOffset",0)
        doc["images"].append({**image,"bufferView":view(target.binary[start:start+old_view["byteLength"]])})
    doc["buffers"] = [{"byteLength":size}]
    encoded = json.dumps(doc,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    encoded += b" "*((-len(encoded))%4)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("wb") as file:
        file.write(struct.pack("<4sII",b"glTF",2,28+len(encoded)+size))
        file.write(struct.pack("<I4s",len(encoded),b"JSON")); file.write(encoded)
        file.write(struct.pack("<I4s",size,b"BIN\0"))
        for chunk in chunks:
            file.write(chunk)
    report = {"source":str(source.path),"source_sha256":hashlib.sha256(source.raw).hexdigest(),
              "texture_source":str(target.path),"texture_source_sha256":hashlib.sha256(target.raw).hexdigest(),
              "output":str(output),"output_sha256":hashlib.sha256(output.read_bytes()).hexdigest(),
              "source_triangles":len(si),"output_triangles":len(indices)//3,"output_vertices":len(positions),
              "matched_faces":int(matched.sum()),"restored_small_faces":len(missing),"largest_restored_face_area":missing_area_max,
              "reviewed_restored_face_area_limit":args.reviewed_area_limit,
              "normalization_scale_in_api_output":scale,"maximum_vertex_match_error":error,
              "maximum_small_face_uv_projection_distance":float(nearby_error.max()) if len(missing) else 0,
              "restored_corners_with_barycentric_uv_projection":projected_corner_count,
              "original_positions_and_triangle_surfaces_preserved":True,"source_file_modified":False,
              "embedded_texture_bytes_modified":False,"requires_independent_geometry_check":True}
    output.with_suffix(".transfer.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
