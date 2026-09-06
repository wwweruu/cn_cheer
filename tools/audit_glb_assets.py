# -*- coding: utf-8 -*-
"""Pure-Python GLB geometry / skinning / animation / texture audit.
No Blender dependency. Reads GLB (12-byte header + JSON chunk + BIN chunk),
parses accessors/bufferViews for POSITION/NORMAL/indices/JOINTS_0/WEIGHTS_0
and animation sampler input/output. Emits JSON; a second step renders Markdown.
"""
import json
import struct
import sys
from pathlib import Path

import numpy as np

COMP_DTYPE = {
    5120: np.int8, 5121: np.uint8, 5122: np.int16,
    5123: np.uint16, 5125: np.uint32, 5126: np.float32,
}
COMP_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
TYPE_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

EXPECTED_CLIPS = ["idle", "attack", "hit", "death", "walk", "run"]
LOOP_CLIPS = {"idle", "walk", "run"}


def parse_glb(path):
    data = Path(path).read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError("not a GLB file")
    version, total_len = struct.unpack_from("<II", data, 4)
    if total_len != len(data):
        raise ValueError(f"length mismatch header={total_len} actual={len(data)}")
    off = 12
    gltf = None
    bin_chunk = b""
    while off + 8 <= len(data):
        clen, ctype = struct.unpack_from("<II", data, off)
        off += 8
        chunk = data[off:off + clen]
        off += clen
        if ctype == 0x4E4F534A:  # JSON
            gltf = json.loads(chunk.decode("utf-8"))
        elif ctype == 0x004E4942:  # BIN
            bin_chunk = chunk
    if gltf is None:
        raise ValueError("no JSON chunk")
    return gltf, bin_chunk


def read_accessor(gltf, bin_chunk, idx):
    """Return numpy array shaped (count, ncomp). Handles byteStride. No sparse."""
    acc = gltf["accessors"][idx]
    comp = acc["componentType"]
    ncomp = TYPE_COUNT[acc["type"]]
    count = acc["count"]
    if acc.get("sparse"):
        raise ValueError("sparse accessor unsupported")
    dtype = COMP_DTYPE[comp]
    if "bufferView" not in acc:
        return np.zeros((count, ncomp), dtype=dtype)
    bv = gltf["bufferViews"][acc["bufferView"]]
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or COMP_SIZE[comp] * ncomp
    item = COMP_SIZE[comp] * ncomp
    if stride == item:
        arr = np.frombuffer(bin_chunk, dtype=dtype, count=count * ncomp, offset=base)
    else:
        out = np.empty((count, ncomp), dtype=dtype)
        for i in range(count):
            out[i] = np.frombuffer(bin_chunk, dtype=dtype, count=ncomp,
                                   offset=base + i * stride)
        arr = out.ravel()
    arr = arr.reshape(count, ncomp)
    if acc.get("normalized") and comp in (5120, 5121, 5122, 5123):
        maxv = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}[comp]
        arr = arr.astype(np.float32) / maxv
        if comp in (5120, 5122):
            arr = np.maximum(arr, -1.0)
    return arr


def image_size(buf, mime):
    """Extract (w, h) from PNG/WebP/KTX2 bytes; None if unknown."""
    try:
        if buf[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack_from(">II", buf, 16)
            return w, h
        if buf[:12] == b"\xabKTX 20\xbb\r\n\x1a\n" or buf[1:5] == b"KTX ":
            w, h = struct.unpack_from("<II", buf, 20)
            return w, h
        if buf[:4] == b"RIFF" and buf[8:12] == b"WEBP":
            fmt = buf[12:16]
            if fmt == b"VP8X":
                w = 1 + int.from_bytes(buf[24:27], "little")
                h = 1 + int.from_bytes(buf[27:30], "little")
                return w, h
            if fmt == b"VP8 ":
                w, h = struct.unpack_from("<HH", buf, 26)
                return w & 0x3FFF, h & 0x3FFF
            if fmt == b"VP8L":
                b = buf[21:25]
                bits = int.from_bytes(b, "little")
                w = (bits & 0x3FFF) + 1
                h = ((bits >> 14) & 0x3FFF) + 1
                return w, h
    except Exception:
        return None
    return None


def quat_angle_deg(a, b):
    d = abs(float(np.dot(a, b)))
    d = min(d, 1.0)
    return float(np.degrees(2.0 * np.arccos(d)))


def audit_file(path, root):
    rel = str(Path(path).relative_to(root)).replace("\\", "/")
    rec = {"file": rel, "size_mb": round(Path(path).stat().st_size / 1e6, 2),
           "error": None, "meshes": [], "vertices": 0, "triangles": 0,
           "bbox": None, "skinning": None, "animations": [], "images": [],
           "problems": []}
    try:
        gltf, bin_chunk = parse_glb(path)
    except Exception as e:
        rec["error"] = str(e)
        rec["problems"].append({"sev": "error", "check": "parse", "detail": str(e)})
        return rec

    accessors = gltf.get("accessors", [])
    nodes = gltf.get("nodes", [])
    skins = gltf.get("skins", [])
    node_names = [n.get("name", f"node{i}") for i, n in enumerate(nodes)]

    # ---------- geometry ----------
    mins, maxs = [], []
    for mi, mesh in enumerate(gltf.get("meshes", [])):
        mname = mesh.get("name", f"mesh{mi}")
        for pi, prim in enumerate(mesh.get("primitives", [])):
            pm = {"mesh": mname, "prim": pi, "vertices": 0, "triangles": 0,
                  "degenerate_ratio": None, "normal_issue": None}
            attrs = prim.get("attributes", {})
            if "POSITION" not in attrs:
                rec["problems"].append({"sev": "warn", "check": "geometry",
                                        "detail": f"{mname}[{pi}] no POSITION"})
                continue
            try:
                pos = read_accessor(gltf, bin_chunk, attrs["POSITION"]).astype(np.float64)
            except Exception as e:
                rec["problems"].append({"sev": "error", "check": "geometry",
                                        "detail": f"{mname}[{pi}] POSITION read failed: {e}"})
                continue
            nv = pos.shape[0]
            pm["vertices"] = nv
            rec["vertices"] += nv

            # NaN / Inf
            bad = int((~np.isfinite(pos)).sum())
            if bad:
                rec["problems"].append({"sev": "error", "check": "nan",
                    "detail": f"{mname}[{pi}] POSITION NaN/Inf components: {bad} of {pos.size}"})

            pmin = np.nanmin(pos, axis=0)
            pmax = np.nanmax(pos, axis=0)
            mins.append(pmin)
            maxs.append(pmax)

            # indices
            if "indices" in prim:
                try:
                    ind = read_accessor(gltf, bin_chunk, prim["indices"]).ravel().astype(np.int64)
                except Exception as e:
                    rec["problems"].append({"sev": "error", "check": "geometry",
                                            "detail": f"{mname}[{pi}] indices read failed: {e}"})
                    ind = None
                if ind is not None and ind.size:
                    oob = int(((ind < 0) | (ind >= nv)).sum())
                    if oob:
                        rec["problems"].append({"sev": "error", "check": "index_oob",
                            "detail": f"{mname}[{pi}] {oob} indices out of range (n={nv}, max={int(ind.max())})"})
                    mode = prim.get("mode", 4)
                    if mode == 4:
                        ntri = ind.size // 3
                        pm["triangles"] = ntri
                        rec["triangles"] += ntri
                        tris = ind[:ntri * 3].reshape(ntri, 3)
                        valid = (tris < nv).all(axis=1)
                        if valid.any():
                            tv = pos[tris[valid]]
                            area2 = np.linalg.norm(
                                np.cross(tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0]), axis=1)
                            scale = float(np.linalg.norm(pmax - pmin)) or 1.0
                            thr = (scale * 1e-6) ** 2
                            deg = float((area2 < thr).mean())
                            pm["degenerate_ratio"] = round(deg, 5)
                            if deg > 0.01:
                                rec["problems"].append({"sev": "warn", "check": "degenerate",
                                    "detail": f"{mname}[{pi}] degenerate tris {deg*100:.2f}% ({int((area2<thr).sum())}/{ntri})"})
            else:
                # non-indexed
                ntri = nv // 3
                pm["triangles"] = ntri
                rec["triangles"] += ntri

            # normals
            if "NORMAL" in attrs:
                try:
                    nor = read_accessor(gltf, bin_chunk, attrs["NORMAL"]).astype(np.float64)
                    ln = np.linalg.norm(nor, axis=1)
                    nonzero = ln[ln > 1e-12]
                    dev = float(np.abs(nonzero - 1.0).max()) if nonzero.size else 1.0
                    zero_ratio = float((ln <= 1e-12).mean())
                    pm["normal_issue"] = {"max_dev": round(dev, 4),
                                          "zero_ratio": round(zero_ratio, 4)}
                    if dev > 0.05 or zero_ratio > 0.001:
                        rec["problems"].append({"sev": "warn", "check": "normal",
                            "detail": f"{mname}[{pi}] normals not unit (max|len-1|={dev:.4f}, zero={zero_ratio*100:.2f}%)"})
                except Exception as e:
                    rec["problems"].append({"sev": "warn", "check": "normal",
                                            "detail": f"{mname}[{pi}] NORMAL read failed: {e}"})
            else:
                pm["normal_issue"] = "missing"
                rec["problems"].append({"sev": "info", "check": "normal",
                                        "detail": f"{mname}[{pi}] missing NORMAL"})
            rec["meshes"].append(pm)

    if mins:
        mn = np.min(np.stack(mins), axis=0)
        mx = np.max(np.stack(maxs), axis=0)
        rec["bbox"] = {"min": [round(float(v), 4) for v in mn],
                       "max": [round(float(v), 4) for v in mx],
                       "diag": round(float(np.linalg.norm(mx - mn)), 4)}

    # ---------- skinning ----------
    has_skin_prim = False
    max_joint_idx = -1
    weight_bad = 0
    weight_total = 0
    skin_prims = 0
    for mi, mesh in enumerate(gltf.get("meshes", [])):
        mname = mesh.get("name", f"mesh{mi}")
        for pi, prim in enumerate(mesh.get("primitives", [])):
            attrs = prim.get("attributes", {})
            if "JOINTS_0" not in attrs and "WEIGHTS_0" not in attrs:
                continue
            has_skin_prim = True
            skin_prims += 1
            if "JOINTS_0" not in attrs or "WEIGHTS_0" not in attrs:
                rec["problems"].append({"sev": "error", "check": "skin",
                    "detail": f"{mname}[{pi}] JOINTS_0/WEIGHTS_0 incomplete"})
                continue
            try:
                j = read_accessor(gltf, bin_chunk, attrs["JOINTS_0"]).astype(np.int64)
                w = read_accessor(gltf, bin_chunk, attrs["WEIGHTS_0"]).astype(np.float64)
            except Exception as e:
                rec["problems"].append({"sev": "error", "check": "skin",
                                        "detail": f"{mname}[{pi}] skin attr read failed: {e}"})
                continue
            if j.size:
                max_joint_idx = max(max_joint_idx, int(j.max()))
                if int(j.min()) < 0:
                    rec["problems"].append({"sev": "error", "check": "skin",
                        "detail": f"{mname}[{pi}] negative joint index {int(j.min())}"})
            wsum = w.sum(axis=1)
            active = wsum > 1e-8
            badmask = active & (np.abs(wsum - 1.0) > 0.01)
            weight_bad += int(badmask.sum())
            weight_total += int(active.sum())
            if (~active).any():
                rec["problems"].append({"sev": "warn", "check": "skin",
                    "detail": f"{mname}[{pi}] {int((~active).sum())} verts with all-zero weights"})
    max_skin_joints = max((len(s.get("joints", [])) for s in skins), default=0)
    if has_skin_prim:
        rec["skinning"] = {
            "skinned_prims": skin_prims,
            "skins": len(skins),
            "max_skin_joints": max_skin_joints,
            "max_joint_index": max_joint_idx,
            "weight_sum_bad_ratio": round(weight_bad / weight_total, 5) if weight_total else None,
        }
        if max_joint_idx >= max_skin_joints > 0:
            rec["problems"].append({"sev": "error", "check": "skin",
                "detail": f"joint index {max_joint_idx} >= skin joints {max_skin_joints} (out of bounds)"})
        if weight_total and weight_bad / weight_total > 0.001:
            rec["problems"].append({"sev": "warn", "check": "skin",
                "detail": f"weight sum dev>0.01 in {weight_bad}/{weight_total} verts ({weight_bad/weight_total*100:.2f}%)"})
    elif skins:
        rec["skinning"] = {"skinned_prims": 0, "skins": len(skins)}
        rec["problems"].append({"sev": "warn", "check": "skin",
                                "detail": "skins defined but no JOINTS_0/WEIGHTS_0 attributes"})

    # ---------- animations ----------
    for ai, anim in enumerate(gltf.get("animations", [])):
        aname = anim.get("name", f"anim{ai}")
        arec = {"name": aname, "channels": len(anim.get("channels", [])),
                "duration": 0.0, "min_keyframes": None, "targets": [],
                "nan_outputs": 0, "loop": None}
        max_t = 0.0
        min_keys = None
        first_last = []  # (path, diff_desc, severity_value)
        samplers = anim.get("samplers", [])
        for ch in anim.get("channels", []):
            tgt = ch.get("target", {})
            nidx = tgt.get("node")
            cpath = tgt.get("path", "?")
            nname = node_names[nidx] if isinstance(nidx, int) and nidx < len(node_names) else str(nidx)
            arec["targets"].append(f"{nname}.{cpath}")
            si = ch.get("sampler")
            if si is None or si >= len(samplers):
                continue
            smp = samplers[si]
            try:
                tin = read_accessor(gltf, bin_chunk, smp["input"]).ravel().astype(np.float64)
                tout = read_accessor(gltf, bin_chunk, smp["output"]).astype(np.float64)
            except Exception as e:
                rec["problems"].append({"sev": "error", "check": "anim",
                                        "detail": f"{aname}: sampler read failed: {e}"})
                continue
            if tin.size:
                max_t = max(max_t, float(tin.max()))
                min_keys = tin.size if min_keys is None else min(min_keys, tin.size)
            nan_n = int((~np.isfinite(tout)).sum())
            arec["nan_outputs"] += nan_n
            if tout.shape[0] >= 2:
                f0, f1 = tout[0], tout[-1]
                if cpath == "rotation" and f0.shape[0] == 4:
                    d = quat_angle_deg(f0, f1)
                    first_last.append(("rotation", round(d, 2)))
                else:
                    d = float(np.abs(f0 - f1).max())
                    first_last.append((cpath, round(d, 5)))
        arec["duration"] = round(max_t, 3)
        arec["min_keyframes"] = min_keys
        arec["first_last_max"] = first_last
        if arec["nan_outputs"]:
            rec["problems"].append({"sev": "error", "check": "anim_nan",
                "detail": f"clip '{aname}': {arec['nan_outputs']} NaN/Inf sampler output components"})
        if max_t <= 0.0:
            rec["problems"].append({"sev": "error", "check": "anim_duration",
                "detail": f"clip '{aname}': zero duration"})
        if min_keys is not None and min_keys < 2:
            rec["problems"].append({"sev": "warn", "check": "anim_keys",
                "detail": f"clip '{aname}': only {min_keys} keyframe(s)"})
        # loop consistency
        base = aname.lower()
        is_loop = any(k in base for k in LOOP_CLIPS)
        rot_diffs = [v for p, v in first_last if p == "rotation"]
        tr_diffs = [v for p, v in first_last if p == "translation"]
        max_rot = max(rot_diffs) if rot_diffs else 0.0
        max_tr = max(tr_diffs) if tr_diffs else 0.0
        arec["loop"] = {"expected": is_loop, "max_rot_deg": round(max_rot, 2),
                        "max_trans": round(max_tr, 5)}
        if is_loop and (max_rot > 5.0 or max_tr > 0.02):
            rec["problems"].append({"sev": "warn", "check": "loop",
                "detail": f"loop clip '{aname}': first/last pose diff rot={max_rot:.1f}deg trans={max_tr:.4f}"})
        rec["animations"].append(arec)

    # ---------- textures / images ----------
    bvs = gltf.get("bufferViews", [])
    for ii, img in enumerate(gltf.get("images", [])):
        irec = {"name": img.get("name", f"img{ii}"), "mime": img.get("mimeType", "?")}
        if "bufferView" in img:
            bv = bvs[img["bufferView"]]
            start = bv.get("byteOffset", 0)
            buf = bin_chunk[start:start + bv["byteLength"]]
            irec["bytes"] = bv["byteLength"]
            size = image_size(buf, irec["mime"])
            irec["dims"] = size
            if not buf:
                rec["problems"].append({"sev": "error", "check": "texture",
                                        "detail": f"image '{irec['name']}' empty bufferView"})
        elif "uri" in img:
            irec["external_uri"] = img["uri"][:80]
            if img["uri"].startswith("data:"):
                irec["external_uri"] = "data-uri"
            else:
                rec["problems"].append({"sev": "warn", "check": "texture",
                    "detail": f"image '{irec['name']}' external uri (no internal buffer): {img['uri'][:60]}"})
        else:
            rec["problems"].append({"sev": "error", "check": "texture",
                                    "detail": f"image '{irec['name']}' has neither bufferView nor uri"})
        rec["images"].append(irec)
    # materials referencing textures that exist?
    n_tex = len(gltf.get("textures", []))
    if n_tex and not rec["images"]:
        rec["problems"].append({"sev": "error", "check": "texture",
                                "detail": f"{n_tex} textures but no images"})
    rec["n_textures"] = n_tex
    return rec


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else
                r"D:\个人资料\cn_chess\public\assets\models")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else
               r"D:\个人资料\cn_chess\docs\asset-reports\glb-audit-raw.json")
    files = sorted(root.rglob("*.glb"))
    print(f"auditing {len(files)} GLB files", flush=True)
    results = []
    for i, f in enumerate(files):
        try:
            rec = audit_file(f, root)
        except Exception as e:
            rec = {"file": str(f), "error": str(e),
                   "problems": [{"sev": "error", "check": "parse", "detail": str(e)}],
                   "meshes": [], "animations": [], "images": [], "vertices": 0,
                   "triangles": 0, "bbox": None, "skinning": None}
        results.append(rec)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(files)}", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()
