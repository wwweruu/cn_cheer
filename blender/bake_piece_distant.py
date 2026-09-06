"""Rebake a distant derivative onto new UVs, preserving the complete silhouette."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_meshy_sample import repair_normals, reduce_triangles, select_meshes, triangle_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--triangles", type=int, default=12000)
    parser.add_argument("--texture-size", type=int, choices=(1024,2048,4096), default=2048)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    source, output = Path(args.input).resolve(), Path(args.output).resolve()
    assert not output.exists(), "Use a fresh output directory"
    output.mkdir(parents=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if source.suffix.lower()==".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source))
    else:
        bpy.ops.import_scene.gltf(filepath=str(source))
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    assert len(objects) == 1 and len(objects[0].data.materials) == 1
    high = objects[0]
    low = high.copy()
    low.data = high.data.copy()
    bpy.context.collection.objects.link(low)
    repair_normals([low])
    reduce_triangles([low], args.triangles)
    for polygon in low.data.polygons:
        polygon.use_smooth = True
    while low.data.uv_layers:
        low.data.uv_layers.remove(low.data.uv_layers[0])
    select_meshes([low])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.05, island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    original_material = high.data.materials[0]
    source_bsdf = original_material.node_tree.nodes.get("Principled BSDF")
    source_output = next(node for node in original_material.node_tree.nodes if node.type == "OUTPUT_MATERIAL")
    base_texture = source_bsdf.inputs["Base Color"].links[0].from_node
    roughness_node = source_bsdf.inputs["Roughness"].links[0].from_node
    packed_texture = next(socket.links[0].from_node for socket in roughness_node.inputs if socket.links)
    assert base_texture.type == "TEX_IMAGE" and packed_texture.type == "TEX_IMAGE"
    material = bpy.data.materials.new("Distant rebaked PBR")
    material.use_nodes = True
    low.data.materials.clear()
    low.data.materials.append(material)
    nodes, links = material.node_tree.nodes, material.node_tree.links
    target_bsdf = nodes.get("Principled BSDF")
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    preferences = bpy.context.preferences.addons["cycles"].preferences
    preferences.compute_device_type = "OPTIX"
    preferences.get_devices()
    assert any(device.type == "OPTIX" for device in preferences.devices)
    for device in preferences.devices:
        device.use = device.type == "OPTIX"
    scene.cycles.device = "GPU"
    scene.cycles.samples = 8
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.cage_extrusion = 0.01
    scene.render.bake.max_ray_distance = 0.035
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True
    baked = {}
    for channel, colorspace in (("normal", "Non-Color"), ("base", "sRGB"), ("packed", "Non-Color")):
        image = bpy.data.images.new("distant_"+channel, width=args.texture_size, height=args.texture_size, alpha=False)
        image.colorspace_settings.name = colorspace
        node = nodes.new("ShaderNodeTexImage")
        node.image = image
        nodes.active = node
        baked[channel] = node
        select_meshes([high, low])
        bpy.context.view_layer.objects.active = low
        if channel == "normal":
            bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT")
        else:
            emission = original_material.node_tree.nodes.new("ShaderNodeEmission")
            original_material.node_tree.links.new((base_texture if channel == "base" else packed_texture).outputs["Color"], emission.inputs["Color"])
            original_material.node_tree.links.new(emission.outputs[0], source_output.inputs["Surface"])
            bpy.ops.object.bake(type="EMIT")
            original_material.node_tree.nodes.remove(emission)
        image.pack()
        print("BAKED", channel, flush=True)
    original_material.node_tree.links.new(source_bsdf.outputs["BSDF"], source_output.inputs["Surface"])
    links.new(baked["base"].outputs["Color"], target_bsdf.inputs["Base Color"])
    normal = nodes.new("ShaderNodeNormalMap")
    links.new(baked["normal"].outputs["Color"], normal.inputs["Color"])
    links.new(normal.outputs["Normal"], target_bsdf.inputs["Normal"])
    separate = nodes.new("ShaderNodeSeparateColor")
    links.new(baked["packed"].outputs["Color"], separate.inputs["Color"])
    links.new(separate.outputs["Green"], target_bsdf.inputs["Roughness"])
    links.new(separate.outputs["Blue"], target_bsdf.inputs["Metallic"])
    select_meshes([low])
    destination = output / "model.glb"
    bpy.ops.export_scene.gltf(filepath=str(destination), export_format="GLB", use_selection=True,
        export_yup=True, export_image_format="WEBP", export_image_quality=95, export_materials="EXPORT")
    bpy.ops.wm.save_as_mainfile(filepath=str(output/"rebake.blend"), compress=True)
    raw = destination.read_bytes()
    report = {"source":str(source),"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "file":"model.glb","triangles":triangle_count([low]),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
        "texture_resolution":args.texture_size,"new_uv":True,"method":"Selected-to-active normal, base color and metallic/roughness rebake", "requires_visual_review":True}
    (output/"rebake.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("REBAKE_COMPLETE",report["triangles"],len(raw),flush=True)


if __name__ == "__main__":
    main()
