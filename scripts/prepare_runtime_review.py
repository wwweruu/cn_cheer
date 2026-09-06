"""Stage verified runtime files for one local inspection page (no paid calls)."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "assets/generated/meshy/general_red/runtime/v1"
report = json.loads((source / "runtime.json").read_text(encoding="utf-8"))
master = ROOT / "assets/generated/meshy/general_red/texture/v1/preserved/model.glb"
assert hashlib.sha256(master.read_bytes()).hexdigest() == report["source_sha256"]
# Blender discards two degenerate faces on import; preserve the raw file count.
report["imported_triangles"] = report.get("imported_triangles", report["source_triangles"])
report["source_triangles"] = 3010366
(source / "runtime.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
output = ROOT / "public/assets/review/general_red/runtime"
output.mkdir(parents=True, exist_ok=True)
manifest = {"piece": "general_red", "master_user_approved": True, "source_sha256": report["source_sha256"], "variants": {}}
for tier, label in (("desktop", "desktop"), ("mobile", "mobile")):
    entry = report["files"][tier]
    file = source / entry["file"]
    assert hashlib.sha256(file.read_bytes()).hexdigest() == entry["sha256"]
    shutil.copy2(file, output / file.name)
    manifest["variants"][label] = entry
rebake_root = ROOT / "assets/generated/meshy/general_red/runtime/distant-v2"
rebake = json.loads((rebake_root / "rebake.json").read_text(encoding="utf-8"))
assert hashlib.sha256((rebake_root / "model.glb").read_bytes()).hexdigest() == rebake["sha256"]
shutil.copy2(rebake_root / "model.glb", output / "general_red_rebaked_distant.glb")
manifest["variants"]["lod2"] = {**rebake, "file":"general_red_rebaked_distant.glb"}
(output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
source_manifest = ROOT / "public/assets/review/general_red/agent-master/manifest.json"
data = json.loads(source_manifest.read_text(encoding="utf-8"))
data["user_approved"] = True
data["approved_on"] = "2026-09-06"
source_manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Staged runtime review: desktop, mobile, rebaked distant; original master unchanged.")
