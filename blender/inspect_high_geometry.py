"""Render unmodified geometry under common clay lighting for visual comparison.

This script does not export models, simplify geometry or modify the input files.
Only object placement, uniform viewing scale and temporary preview materials change.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_meshy_sample import bounds, triangle_count, aim, area


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--size", type=int, default=900)
    parser.add_argument("--views", default="front,three_quarter,back,detail")
    parser.add_argument("--keep-materials", action="store_true", help="Render imported PBR materials instead of clay")
    parser.add_argument("--gpu", action="store_true", help="Use an available OptiX device for the preview")
    parser.add_argument("--fit-object", action="store_true", help="Fit the longest dimension for broad scene models")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    source, output = Path(args.input).resolve(), Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "geometry.json").exists():
        raise RuntimeError("Choose a fresh comparison directory")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    low, high = bounds(objects)
    before = triangle_count(objects)
    scale = 2 / (max(high-low) if args.fit_object else high.z-low.z)
    center = Vector(((high.x + low.x) / 2, (high.y + low.y) / 2, low.z))
    transform = Matrix.Scale(scale, 4) @ Matrix.Translation(-center)
    material = bpy.data.materials.new("Temporary neutral clay")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.40, 0.44, 0.48, 1)
    bsdf.inputs["Roughness"].default_value = 0.65
    for obj in objects:
        obj.matrix_world = transform @ obj.matrix_world
        if not args.keep_materials:
            obj.data.materials.clear()
            obj.data.materials.append(material)
            for polygon in obj.data.polygons:
                polygon.material_index = 0
                polygon.use_smooth = True
    bpy.context.view_layer.update()
    after_low, after_high = bounds(objects)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    if args.gpu:
        preferences = bpy.context.preferences.addons["cycles"].preferences
        preferences.compute_device_type = "OPTIX"
        preferences.get_devices()
        assert any(device.type == "OPTIX" for device in preferences.devices), "No OptiX device available"
        for device in preferences.devices:
            device.use = device.type == "OPTIX"
        scene.cycles.device = "GPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = args.size
    scene.render.resolution_y = round(args.size * 1.2)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Inspection world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.06, 0.075, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.4
    scene.world = world
    bpy.ops.mesh.primitive_plane_add(size=100)
    plane = bpy.context.object
    plane.data.materials.append(material)
    plane.location.z = -0.003
    area("Key", (-3, -4, 5), 600, 3, (1, 0.96, 0.91), (0, 0, 1))
    area("Fill", (3, -2, 3), 260, 3, (0.8, 0.9, 1), (0, 0, 1))
    area("Rim", (1, 3, 4), 600, 2, (1, 1, 1), (0, 0, 1))
    camera_data = bpy.data.cameras.new("Inspection camera")
    camera = bpy.data.objects.new("Inspection camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = "ORTHO"
    views = {
        "front": ((0, -4, 1.25), (0, 0, 1), 2.6),
        "three_quarter": ((2.8, -4, 1.65), (0, 0, 1), 2.6),
        "back": ((0, 4, 1.25), (0, 0, 1), 2.6),
        "detail": ((0.55, -3, 1.95), (0, 0, 1.6), 0.9),
        "base": ((0.45, -3, 0.5), (0, 0, 0.3), 0.85),
    }
    if args.fit_object:
        center_z = (after_high.z+after_low.z)/2
        views = {
            "front": ((0,-4,center_z+.5), (0,0,center_z), 2.65),
            "three_quarter": ((2.8,-4,3), (0,0,center_z), 2.65),
            "back": ((0,4,center_z+.5), (0,0,center_z), 2.65),
            "top": ((0,-.001,4), (0,0,center_z), 2.65),
            "low": ((2.8,-4,center_z+.2), (0,0,center_z), 2.65),
        }
    for name in args.views.split(","):
        position, target, ortho = views[name]
        camera.location, camera_data.ortho_scale = position, ortho
        aim(camera, target)
        scene.render.filepath = str(output / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print("INSPECTED", source.name, name, flush=True)
    assert triangle_count(objects) == before
    report = {"input": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "triangles": before, "raw_bounds_blender": {"min": list(low), "max": list(high)},
              "view_scale": scale, "display_bounds": {"min": list(after_low), "max": list(after_high)},
              "geometry_modified": False, "texture_or_normal_map_used": args.keep_materials,
              "views": args.views.split(",")}
    (output / "geometry.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
