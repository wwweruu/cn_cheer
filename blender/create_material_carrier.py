"""UV carrier for native 4K Meshy surface materials, one full UV tile per face."""
from pathlib import Path
import bpy

root = Path(__file__).resolve().parents[1]
output = root / "assets/source/environment"
output.mkdir(parents=True, exist_ok=True)
assert not (output / "material_carrier.glb").exists()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=1)
obj = bpy.context.object
obj.name = "One metre material swatch"
obj.scale.z = .02
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
uv = obj.data.uv_layers.active.data
for face in obj.data.polygons:
    axes = [index for index in range(3) if index != max(range(3), key=lambda i: abs(face.normal[i]))]
    coordinates = [obj.data.vertices[obj.data.loops[index].vertex_index].co for index in face.loop_indices]
    for loop_index, position in zip(face.loop_indices, coordinates):
        uv[loop_index].uv = tuple((position[axis] - min(p[axis] for p in coordinates)) /
                                 (max(p[axis] for p in coordinates) - min(p[axis] for p in coordinates)) for axis in axes)
material = bpy.data.materials.new("Neutral original-UV surface")
material.diffuse_color = (.35, .35, .35, 1)
obj.data.materials.append(material)
bpy.ops.wm.save_as_mainfile(filepath=str(output / "material_carrier.blend"))
bpy.ops.export_scene.gltf(filepath=str(output / "material_carrier.glb"), export_format="GLB", use_selection=True)
print("MATERIAL_CARRIER_READY", flush=True)
