# -*- coding: utf-8 -*-
"""重渲车-红方三视图：EEVEE + 材质 + 更宽的取景"""
import bpy
import os
from mathutils import Vector

ROOT = r"C:\Users\guyu\cn_cheer"
BLEND = os.path.join(ROOT, "blender", "chariot_red.blend")
RENDER_DIR = os.path.join(ROOT, "blender", "renders")

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 768
scene.render.resolution_y = 1152

world = bpy.data.worlds.new("studio")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.55, 0.55, 1.0)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.35

def add_area(name, loc, energy, size=3.0):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.size = size
    o = bpy.data.objects.new(name, data)
    scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector((0, -0.3, 0.8)) - o.location).to_track_quat("-Z", "Y").to_euler()

add_area("key", (2.5, -2.5, 3.5), 320)
add_area("fill", (-2.5, -1.5, 2.5), 180)
add_area("rim", (0, 2.8, 3.0), 240)

cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

# 每视角独立取景范围与目标点（模型纵深大，侧/后视需要更宽）
views = {
    "front": (Vector((0, -4.6, 0.9)), Vector((0, -0.15, 0.9)), 2.15),
    "side":  (Vector((4.6, -0.55, 0.9)), Vector((0, -0.55, 0.9)), 2.3),
    "back":  (Vector((0, 4.2, 0.9)), Vector((0, -0.3, 0.9)), 2.15),
}
for name, (loc, target, ortho) in views.items():
    cam.location = loc
    cam_data.ortho_scale = ortho
    cam.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(RENDER_DIR, f"chariot_red_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", scene.render.filepath)

print("DONE-RERENDER")
