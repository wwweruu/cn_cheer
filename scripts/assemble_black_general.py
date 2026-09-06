"""Combine the long-cloak body and the independently generated named pedestal.

Both paid originals remain intact. This explicit local assembly is the texture
source; it is never described as an untouched API generation.
"""
import hashlib
import json
from pathlib import Path
import struct

from restore_source_geometry import GLB, np

ROOT = Path(__file__).resolve().parents[1]
body_path = ROOT / "assets/generated/meshy/general_black/v1/model.glb"
base_path = ROOT / "assets/generated/meshy/general_black/v2/model.glb"
output = ROOT / "assets/generated/meshy/general_black/assembled/v2"
output.mkdir(parents=True, exist_ok=True)
assert not (output / "model.glb").exists(), "Use a fresh assembly version"
body, base = GLB(body_path), GLB(base_path)
bp, bi = body.attribute("POSITION").copy(), body.triangles().copy()
pp, pi = base.attribute("POSITION"), base.triangles()
deck = -0.738
base_cut = -0.735
mask = pp[pi, 1].max(axis=1) <= base_cut
picked = pi[mask]
used, inverse = np.unique(picked.ravel(), return_inverse=True)
pedestal = pp[used].copy()
pedestal[:, [0, 2]] *= 0.88
base_indices = inverse.reshape(-1, 3).astype("<u4")
# Match the complete body's height to the body above the single-image pedestal.
scale = float((pp[:, 1].max() - deck) / (bp[:, 1].max() - bp[:, 1].min()))
translation = np.array([0, deck - float(bp[:, 1].min()) * scale, 0])
bp = (bp.astype(np.float64) * scale + translation).astype("<f4")
positions = np.concatenate([bp, pedestal]).astype("<f4")
indices = np.concatenate([bi, base_indices + len(bp)]).astype("<u4")
# A thin cap closes the foot contact holes left when separating the fused base.
# It sits just above the old deck and inside the raised outer lip.
count = 256
angle = np.arange(count) * (2 * np.pi / count)
cx, cz = float((pedestal[:, 0].min()+pedestal[:, 0].max())*.5), float((pedestal[:, 2].min()+pedestal[:, 2].max())*.5)
rx, rz = float((pedestal[:, 0].max()-pedestal[:, 0].min())*.5*.93), float((pedestal[:, 2].max()-pedestal[:, 2].min())*.5*.93)
cap = np.column_stack([cx+np.cos(angle)*rx, np.full(count, deck+.001), cz+np.sin(angle)*rz]).astype("<f4")
cap = np.concatenate([np.array([[cx,deck+.001,cz]],dtype="<f4"),cap])
cap_indices = np.array([[0,1+(i+1)%count,1+i] for i in range(count)],dtype="<u4") + len(positions)
positions = np.concatenate([positions,cap])
indices = np.concatenate([indices,cap_indices])
raw_p, raw_i = positions.tobytes(), indices.tobytes()
doc = {"asset":{"version":"2.0","generator":"cn-chess local black-general body and base assembly"},
    "scene":0,"scenes":[{"nodes":[0]}],"nodes":[{"mesh":0}],
    "meshes":[{"primitives":[{"attributes":{"POSITION":0},"indices":1,"mode":4}]}],
    "buffers":[{"byteLength":len(raw_p)+len(raw_i)}],
    "bufferViews":[{"buffer":0,"byteOffset":0,"byteLength":len(raw_p),"target":34962},
                   {"buffer":0,"byteOffset":len(raw_p),"byteLength":len(raw_i),"target":34963}],
    "accessors":[{"bufferView":0,"componentType":5126,"count":len(positions),"type":"VEC3",
                  "min":positions.min(axis=0).tolist(),"max":positions.max(axis=0).tolist()},
                 {"bufferView":1,"componentType":5125,"count":indices.size,"type":"SCALAR"}]}
encoded = json.dumps(doc,separators=(",",":")).encode()
encoded += b" "*(-len(encoded)%4)
binary = raw_p+raw_i
raw = struct.pack("<4sII",b"glTF",2,28+len(encoded)+len(binary))+struct.pack("<I4s",len(encoded),b"JSON")+encoded+struct.pack("<I4s",len(binary),b"BIN\0")+binary
(output/"model.glb").write_bytes(raw)
report = {"piece":"general_black","body_source":str(body_path),"body_sha256":hashlib.sha256(body.raw).hexdigest(),
    "base_source":str(base_path),"base_sha256":hashlib.sha256(base.raw).hexdigest(),"body_triangles_preserved":len(bi),
    "body_uniform_scale":scale,"body_translation":translation.tolist(),"base_horizontal_scale":.88,
    "base_triangles_extracted":len(base_indices),"base_cut_y":base_cut,"cap_triangles":count,
    "triangles":len(indices),"sha256":hashlib.sha256(raw).hexdigest(),"original_files_unchanged":True,
    "visual_review_required":True,"reference_note":"Black cloak is open at the back in the supplied back view; retain long side panels and visible rear armor."}
(output/"assembly.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:report[k] for k in ['triangles','body_triangles_preserved','base_triangles_extracted','sha256']}))
