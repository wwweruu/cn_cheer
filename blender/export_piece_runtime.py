"""Export bounded runtime derivatives of an approved complete textured master.

No source geometry is overwritten and no new base is synthesized. UVs and PBR
are carried through simplification. Inspect rendered derivatives before staging.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_meshy_sample import bounds, repair_normals, reduce_triangles, select_meshes, triangle_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--piece", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    source, output = Path(args.input).resolve(), Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("Choose a fresh runtime directory")
    output.mkdir(parents=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    assert objects and not any(obj.type == "ARMATURE" for obj in bpy.context.scene.objects)
    imported_triangles = triangle_count(objects)
    raw_source = source.read_bytes()
    document = json.loads(raw_source[20:20 + struct.unpack_from("<I", raw_source, 12)[0]])
    original_triangles = sum(document["accessors"][primitive.get("indices", primitive["attributes"]["POSITION"])]["count"] // 3
        for mesh in document["meshes"] for primitive in mesh["primitives"])
    for obj in objects:
        world = obj.matrix_world.copy()
        obj.data = obj.data.copy()
        obj.parent = None
        obj.data.transform(world)
        obj.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    low, high = bounds(objects)
    dimensions = high - low
    scale = min(1.72 / dimensions.z, 0.90 / max(dimensions.x, dimensions.y))
    center = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
    transform = Matrix.Scale(scale, 4) @ Matrix.Translation(-center)
    for obj in objects:
        obj.data.transform(transform)
    bpy.context.view_layer.update()
    source_low, source_high = bounds(objects)
    images = [image for image in bpy.data.images if image.type == "IMAGE" and image.size[0] > 0]
    report = {"piece": args.piece, "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_triangles": original_triangles, "imported_triangles": imported_triangles,
        "source_images": [{"name": image.name, "size": list(image.size)} for image in images],
        "normalization_scale": scale, "base_added": False, "source_unchanged": True,
        "requires_visual_review": True, "files": {}}
    for image in images:
        if not image.packed_file:
            image.pack()
    select_meshes(objects)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / (args.piece + "_source.blend")), compress=True)
    repair_normals(objects)
    for tier, maximum, tex_size in (("desktop", 60000, 4096), ("mobile", 20000, 2048)):
        reduce_triangles(objects, maximum)
        bpy.context.view_layer.update()
        low, high = bounds(objects)
        # Detect destructive normalization/simplification errors, not artistic quality.
        assert max(abs(low[i] - source_low[i]) for i in range(3)) < 0.02
        assert max(abs(high[i] - source_high[i]) for i in range(3)) < 0.02
        for image in images:
            width, height = image.size
            if max(width, height) > tex_size:
                factor = tex_size / max(width, height)
                image.scale(round(width * factor), round(height * factor))
                image.pack()
        select_meshes(objects)
        destination = output / f"{args.piece}_{tier}.glb"
        bpy.ops.export_scene.gltf(filepath=str(destination), export_format="GLB", use_selection=True,
            export_yup=True, export_image_format="WEBP", export_image_quality=95, export_materials="EXPORT")
        data = destination.read_bytes()
        report["files"][tier] = {"file": destination.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "triangles": triangle_count(objects), "images": [{"name": image.name, "size": list(image.size)} for image in images],
            "bounds": {"min": list(low), "max": list(high)}}
        print("RUNTIME_EXPORTED", tier, report["files"][tier]["triangles"], len(data), flush=True)
    report["distant_followup"] = "Run bake_piece_distant.py on the desktop GLB; direct 6K-face UV reuse was rejected."
    (output / "runtime.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
