"""Build closed-surface LODs and bake the full-detail candidate.

Blender --background --python this.py -- --source DIR --output DIR
The 4K/2K LOD0 and its review renders are copied unchanged; no Meshy calls.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_meshy_sample import repair_normals, reduce_triangles, select_meshes, triangle_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    source, output = Path(args.source).resolve(), Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("Choose a fresh review directory")
    output.mkdir(parents=True)
    for name in ("general_red_source.blend", "general_red_desktop.glb", "general_red_mobile.glb",
                 "review_front.png", "review_three_quarter.png", "review_back.png", "review_detail.png"):
        shutil.copy2(source / name, output / name)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source / "general_red_desktop.glb"))
    original = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    body = max(original, key=lambda obj: triangle_count([obj]))
    base = next(obj for obj in original if obj != body)
    # Use world-space geometry for all selected-to-active bake operations.
    for obj in original:
        obj.data.transform(obj.matrix_world)
        obj.matrix_world = Matrix.Identity(4)
    dense = body.copy()
    dense.data = body.data.copy()
    bpy.context.collection.objects.link(dense)
    repair_normals([dense])
    select_meshes([dense])
    dense.data.remesh_voxel_size = 0.006
    dense.data.remesh_voxel_adaptivity = 0
    bpy.ops.object.voxel_remesh()
    modifier = dense.modifiers.new("Smooth reconstructed surface", "SMOOTH")
    modifier.factor, modifier.iterations = 0.5, 3
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    print("CLOSED_SURFACE", triangle_count([dense]), flush=True)
    dense.hide_render = True
    base.hide_render = True
    source_material = body.data.materials[0]
    bsdf = source_material.node_tree.nodes.get("Principled BSDF")
    output_node = next(node for node in source_material.node_tree.nodes if node.type == "OUTPUT_MATERIAL")
    base_texture = bsdf.inputs["Base Color"].links[0].from_node
    image_nodes = [node for node in source_material.node_tree.nodes if node.type == "TEX_IMAGE"]
    packed_texture = next(node for node in image_nodes if node.image.name == "Image_1")
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 8
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.cage_extrusion = 0.012
    scene.render.bake.max_ray_distance = 0.045
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True
    report = json.loads((source / "review.json").read_text(encoding="utf-8"))
    for label, body_budget, base_budget in (("lod1", 7100, 800), ("lod2", 2350, 550)):
        low_body, low_base = dense.copy(), base.copy()
        low_body.data, low_base.data = dense.data.copy(), base.data.copy()
        bpy.context.collection.objects.link(low_body)
        bpy.context.collection.objects.link(low_base)
        low_body.hide_render, low_base.hide_render = False, True
        low_body.name, low_base.name = f"general_red_{label}_body", f"general_red_{label}_base"
        while low_body.data.uv_layers:
            low_body.data.uv_layers.remove(low_body.data.uv_layers[0])
        reduce_triangles([low_body], body_budget)
        reduce_triangles([low_base], base_budget)
        for polygon in low_body.data.polygons:
            polygon.use_smooth = True
        select_meshes([low_body])
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.003)
        bpy.ops.object.mode_set(mode="OBJECT")
        material = bpy.data.materials.new(f"General {label} rebaked PBR")
        material.use_nodes = True
        low_body.data.materials.clear()
        low_body.data.materials.append(material)
        target_bsdf = material.node_tree.nodes.get("Principled BSDF")
        texture_nodes = {}
        for channel, colorspace in (("normal", "Non-Color"), ("base", "sRGB"), ("packed", "Non-Color")):
            image = bpy.data.images.new(f"{label}_{channel}", width=2048, height=2048, alpha=False)
            image.colorspace_settings.name = colorspace
            node = material.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = image
            material.node_tree.nodes.active = node
            texture_nodes[channel] = node
            select_meshes([body, low_body])
            bpy.context.view_layer.objects.active = low_body
            if channel == "normal":
                source_material.node_tree.links.new(bsdf.outputs["BSDF"], output_node.inputs["Surface"])
                bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT")
            else:
                emission = source_material.node_tree.nodes.new("ShaderNodeEmission")
                source_material.node_tree.links.new((base_texture if channel == "base" else packed_texture).outputs["Color"], emission.inputs["Color"])
                source_material.node_tree.links.new(emission.outputs[0], output_node.inputs["Surface"])
                bpy.ops.object.bake(type="EMIT")
                source_material.node_tree.nodes.remove(emission)
            image.pack()
            print("BAKED", label, channel, flush=True)
        source_material.node_tree.links.new(bsdf.outputs["BSDF"], output_node.inputs["Surface"])
        material.node_tree.links.new(texture_nodes["base"].outputs["Color"], target_bsdf.inputs["Base Color"])
        normal = material.node_tree.nodes.new("ShaderNodeNormalMap")
        material.node_tree.links.new(texture_nodes["normal"].outputs["Color"], normal.inputs["Color"])
        material.node_tree.links.new(normal.outputs["Normal"], target_bsdf.inputs["Normal"])
        split = material.node_tree.nodes.new("ShaderNodeSeparateColor")
        material.node_tree.links.new(texture_nodes["packed"].outputs["Color"], split.inputs["Color"])
        material.node_tree.links.new(split.outputs["Green"], target_bsdf.inputs["Roughness"])
        material.node_tree.links.new(split.outputs["Blue"], target_bsdf.inputs["Metallic"])
        low_base.hide_render = False
        select_meshes([low_body, low_base])
        destination = output / f"general_red_{label}.glb"
        bpy.ops.export_scene.gltf(filepath=str(destination), export_format="GLB", use_selection=True,
                                  export_yup=True, export_image_format="WEBP", export_image_quality=95, export_materials="EXPORT")
        payload = destination.read_bytes()
        report["files"][destination.name] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        report["lod_triangles"][label] = triangle_count([low_body, low_base])
        bpy.ops.wm.save_as_mainfile(filepath=str(output / f"general_red_{label}_bake.blend"))
        low_body.hide_render, low_base.hide_render = True, True
        bpy.data.objects.remove(low_body, do_unlink=True)
        bpy.data.objects.remove(low_base, do_unlink=True)
        print("LOD_COMPLETE", label, report["lod_triangles"][label], flush=True)
    report["lod_method"] = "Closed-surface voxel remesh, simplification, new UVs, selected-to-active PBR bake"
    (output / "review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
