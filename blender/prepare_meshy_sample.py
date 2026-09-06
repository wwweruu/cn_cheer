"""Normalize one static Meshy candidate, export 4K/2K GLBs and render review views.

Run with Blender --background --python this_file -- --input model.glb --output DIR.
Original API files remain untouched. This does not mark the sample as approved.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector


def options():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--yaw-degrees", type=float, default=0)
    parser.add_argument("--render-size", type=int, default=1200)
    parser.add_argument("--add-base", action="store_true", help="Add a deterministic red general pedestal when absent from the generated mesh")
    parser.add_argument("--proof-only", action="store_true", help="Render/export tool test, never claim generated art")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def bounds(objects):
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    return low, high


def triangle_count(objects):
    count = 0
    for obj in objects:
        obj.data.calc_loop_triangles()
        count += len(obj.data.loop_triangles)
    return count


def select_meshes(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def area(name, location, power, size, color, target):
    light = bpy.data.lights.new(name, "AREA")
    light.energy, light.shape, light.size, light.color = power, "DISK", size, color
    obj = bpy.data.objects.new(name, light)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)


def reduce_triangles(objects, maximum):
    for _ in range(5):
        count = triangle_count(objects)
        if count <= maximum:
            return
        ratio = max(0.01, (maximum - max(len(objects) * 16, 80)) / count)
        for obj in objects:
            bpy.context.view_layer.objects.active = obj
            modifier = obj.modifiers.new("Runtime triangle budget", "DECIMATE")
            modifier.ratio = ratio
            modifier.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            obj.data.validate(clean_customdata=True)
    if triangle_count(objects) > maximum:
        raise RuntimeError(f"Unable to meet {maximum} triangle budget: actual {triangle_count(objects)}")


def repair_normals(objects):
    # glTF splits vertices at UV/normal seams. Weld position duplicates while
    # retaining per-corner UVs, then discard imported custom split normals.
    for obj in objects:
        mesh = obj.data
        if mesh.has_custom_normals:
            mesh.normals_split_custom_set([(0, 0, 0)] * len(mesh.loops))
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.000001)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        mesh.validate(clean_customdata=True)
        mesh.update()
    select_meshes(objects)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(60), keep_sharp_edges=False)


def add_base(objects):
    for obj in objects:
        obj.data.transform(Matrix.Translation((0, 0, 0.135)))
    lacquer = bpy.data.materials.new("Red lacquer pedestal")
    lacquer.diffuse_color = (0.12, 0.016, 0.02, 1)
    lacquer.use_nodes = True
    bsdf = lacquer.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = lacquer.diffuse_color
    bsdf.inputs["Metallic"].default_value = 0.18
    bsdf.inputs["Roughness"].default_value = 0.30
    gold = bpy.data.materials.new("Pedestal bronze lettering")
    gold.diffuse_color = (0.52, 0.30, 0.09, 1)
    gold.use_nodes = True
    bsdf = gold.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = gold.diffuse_color
    bsdf.inputs["Metallic"].default_value = 0.82
    bsdf.inputs["Roughness"].default_value = 0.32
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.435, depth=0.125, location=(0, 0, 0.0625))
    base = bpy.context.object
    base.name = "general_red_pedestal"
    base.data.materials.append(lacquer)
    bevel = base.modifiers.new("Rounded lacquer edges", "BEVEL")
    bevel.width, bevel.segments = 0.009, 3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    objects.append(base)
    for z in (0.017, 0.11):
        bpy.ops.mesh.primitive_torus_add(major_segments=64, minor_segments=8, major_radius=0.431,
                                         minor_radius=0.004, location=(0, 0, z))
        obj = bpy.context.object
        obj.name = "general_red_pedestal_rim"
        obj.data.materials.append(gold)
        objects.append(obj)
    font_path = Path("C:/Windows/Fonts/simkai.ttf")
    if not font_path.exists():
        raise RuntimeError("KaiTi font required for a verified Chinese general label")
    curve = bpy.data.curves.new("General label", "FONT")
    curve.body, curve.align_x, curve.align_y = "帅", "CENTER", "CENTER"
    curve.font = bpy.data.fonts.load(str(font_path))
    curve.size, curve.extrude, curve.bevel_depth = 0.105, 0.0008, 0
    curve.resolution_u = 2
    label = bpy.data.objects.new("general_red_label", curve)
    bpy.context.collection.objects.link(label)
    label.location = (0, -0.438, 0.063)
    label.rotation_euler = (math.pi / 2, 0, 0)
    label.data.materials.append(gold)
    select_meshes([label])
    bpy.ops.object.convert(target="MESH")
    objects.append(bpy.context.object)
    # Join the base parts; shared bronze material becomes one draw primitive.
    base_objects = [obj for obj in objects if obj.name.startswith("general_red_")]
    select_meshes(base_objects)
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.join()
    objects[:] = [obj for obj in objects if obj not in base_objects] + [base]


def main():
    args = options()
    source, output = Path(args.input).resolve(), Path(args.output).resolve()
    if source == output or source.is_relative_to(output):
        raise RuntimeError("Output must not contain or replace the input model")
    output.mkdir(parents=True, exist_ok=True)
    if (output / "review.json").exists():
        raise RuntimeError("Review output already exists; choose a new revision directory")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not objects or any(obj.type == "ARMATURE" for obj in bpy.context.scene.objects):
        raise RuntimeError("This preparer expects an unrigged static mesh candidate")
    # Bake imported node transforms into independent mesh data before normalization.
    for obj in objects:
        world = obj.matrix_world.copy()
        obj.data = obj.data.copy()
        obj.parent = None
        obj.data.transform(world)
        obj.matrix_world = Matrix.Identity(4)
    yaw = Matrix.Rotation(math.radians(args.yaw_degrees), 4, "Z")
    for obj in objects:
        obj.data.transform(yaw)
    bpy.context.view_layer.update()
    low, high = bounds(objects)
    dimensions = high - low
    if min(dimensions) <= 0:
        raise RuntimeError("Degenerate model bounds")
    scale = min(1.72 / dimensions.z, 0.90 / max(dimensions.x, dimensions.y))
    center = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
    transform = Matrix.Scale(scale, 4) @ Matrix.Translation(-center)
    for obj in objects:
        obj.data.transform(transform)
    repair_normals(objects)
    if args.add_base:
        add_base(objects)
    select_meshes(objects)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(60), keep_sharp_edges=False)
    bpy.context.view_layer.update()
    low, high = bounds(objects)
    dimensions = high - low
    originals = [image for image in bpy.data.images if image.type == "IMAGE" and image.size[0] > 0]
    image_report = [{"name": image.name, "width": image.size[0], "height": image.size[1],
                     "color_space": image.colorspace_settings.name} for image in originals]
    material_count = len({slot.material.name for obj in objects for slot in obj.material_slots if slot.material})
    for image in originals:
        if not image.packed_file:
            image.pack()
    select_meshes(objects)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "general_red_source.blend"))
    reduce_triangles(objects, 20000)
    files = {}
    # Progressive downscaling; preserve the packed high-resolution blend above.
    desktop_counts = {"lod0": triangle_count(objects)}
    for label, maximum in (("desktop", 4096), ("mobile", 2048)):
        for image in originals:
            width, height = image.size
            if max(width, height) > maximum:
                factor = maximum / max(width, height)
                image.scale(max(1, round(width * factor)), max(1, round(height * factor)))
                image.pack()
        select_meshes(objects)
        destination = output / f"general_red_{label}.glb"
        bpy.ops.export_scene.gltf(filepath=str(destination), export_format="GLB", use_selection=True,
                                  export_yup=True, export_image_format="WEBP", export_image_quality=95, export_materials="EXPORT")
        payload = destination.read_bytes()
        files[destination.name] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    # Lower geometric LODs require rebuilding the surface and rebaking UVs.
    # Run bake_sample_lods.py on this directory before staging the full set.
    # Render the 4K export rather than the now-downscaled mobile images.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(output / "general_red_desktop.glb"))
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    low, high = bounds(objects)
    height = high.z - low.z
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 40 if not args.proof_only else 8
    scene.cycles.use_denoising = True
    scene.render.resolution_x = args.render_size
    scene.render.resolution_y = round(args.render_size * 1.2)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Neutral studio")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.12, 0.14, 0.17, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.35
    scene.world = world
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.003))
    ground = bpy.context.object
    ground.name = "REVIEW_GROUND_NOT_ASSET"
    mat = bpy.data.materials.new("Review neutral floor")
    mat.diffuse_color = (0.095, 0.11, 0.13, 1)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = mat.diffuse_color
    mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
    ground.data.materials.append(mat)
    target = (0, 0, height * 0.5)
    area("Key", (-2.5, -3.5, 4), 450, 3, (1, 0.90, 0.78), target)
    area("Fill", (3, -1.8, 2.5), 240, 3, (0.72, 0.83, 1), target)
    area("Rim", (0.5, 2.8, 3.6), 520, 2, (1, 0.80, 0.56), target)
    camera_data = bpy.data.cameras.new("Review camera")
    camera = bpy.data.objects.new("Review camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = height * 1.28
    views = {
        "front": ((0, -4, height * 0.60), target, height * 1.28),
        "three_quarter": ((2.8, -4, height * 0.85), target, height * 1.28),
        "back": ((0, 4, height * 0.60), target, height * 1.28),
        "detail": ((0.65, -3, height * 0.95), (0, 0, height * 0.76), height * 0.62),
    }
    for name, (position, look_at, ortho_scale) in views.items():
        camera.location = position
        camera_data.ortho_scale = ortho_scale
        aim(camera, look_at)
        scene.render.filepath = str(output / f"review_{name}.png")
        bpy.ops.render.render(write_still=True)
        print("REVIEW_RENDER", name, flush=True)
    report = {"piece": "general_red", "source": str(source), "tool_test_only": args.proof_only,
              "user_approved": False, "triangles": triangle_count(objects), "mesh_objects": len(objects),
              "materials": material_count, "source_images": image_report,
              "lod_triangles": desktop_counts,
              "bounds_meters": {"min": list(low), "max": list(high)}, "files": files,
              "requires_review": ["face and hands", "armor details", "cape and weapon separation", "base lettering", "in-game scale"]}
    (output / "review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("REVIEW_COMPLETE", str(output), flush=True)


if __name__ == "__main__":
    main()
