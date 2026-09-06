#!/usr/bin/env python3
"""Build GitHub Release asset zips (store mode, paths prefixed with public/assets/)."""
import os
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "dist-release")
os.makedirs(OUT, exist_ok=True)

PROD = "public/assets/models/production"
MOTION = "public/assets/models/motion"

PACKAGES = [
    ("cn_chess-1.0.0-assets-base.zip", [
        "public/assets/environment",
        "public/assets/board",
        "public/assets/decoders",
        "public/assets/production-manifest.json",
        "public/assets/motion-manifest.json",
    ] + [f"public/assets/models/{n}" for n in [
        "advisor_black.glb", "advisor_red.glb", "cannon_black.glb", "cannon_red.glb",
        "chariot_black.glb", "chariot_red.glb", "elephant_black.glb", "elephant_red.glb",
        "general_black.glb", "general_red.glb", "horse_black.glb", "horse_red.glb",
        "soldier_black.glb", "soldier_red.glb",
    ]]),
    ("cn_chess-1.0.0-assets-production-a.zip", [
        f"{PROD}/elephant_black", f"{PROD}/chariot_red", f"{PROD}/elephant_red",
        f"{PROD}/horse_black", f"{PROD}/advisor_black", f"{PROD}/general_red",
        f"{PROD}/general_black",
    ]),
    ("cn_chess-1.0.0-assets-production-b.zip", [
        f"{PROD}/soldier_black", f"{PROD}/soldier_red", f"{PROD}/cannon_red",
        f"{PROD}/horse_red", f"{PROD}/chariot_black", f"{PROD}/cannon_black",
        f"{PROD}/advisor_red",
    ]),
    ("cn_chess-1.0.0-assets-motion-a.zip", [
        f"{MOTION}/elephant_black", f"{MOTION}/chariot_red", f"{MOTION}/elephant_red",
        f"{MOTION}/horse_black", f"{MOTION}/advisor_black", f"{MOTION}/chariot_black",
        f"{MOTION}/cannon_black",
    ]),
    ("cn_chess-1.0.0-assets-motion-b.zip", [
        f"{MOTION}/soldier_black", f"{MOTION}/soldier_red", f"{MOTION}/cannon_red",
        f"{MOTION}/horse_red", f"{MOTION}/general_red", f"{MOTION}/general_black",
        f"{MOTION}/advisor_red",
    ]),
    ("cn_chess-1.0.0-assets-native-motion.zip", [
        "public/assets/models/native-motion",
    ]),
]


def iter_files(rel):
    abs_path = os.path.join(ROOT, rel)
    if os.path.isfile(abs_path):
        yield abs_path, rel.replace(os.sep, "/")
        return
    for dirpath, _dirnames, filenames in os.walk(abs_path):
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            arc = os.path.relpath(full, ROOT).replace(os.sep, "/")
            yield full, arc


for name, entries in PACKAGES:
    dest = os.path.join(OUT, name)
    count = 0
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED,
                         compresslevel=None, allowZip64=True) as zf:
        for rel in entries:
            for full, arc in iter_files(rel):
                assert arc.startswith("public/assets/"), arc
                zf.write(full, arc)
                count += 1
    size = os.path.getsize(dest)
    print(f"{name}: {count} files, {size} bytes ({size/1024/1024:.1f} MiB)", flush=True)

print("DONE")
