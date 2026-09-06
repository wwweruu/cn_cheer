"""Inspect PBR channels around the general's boot/cape boundary."""
import json
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'assets/generated/meshy/general_black/runtime/v1/general_black_desktop.glb'))
mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
mesh.data.transform(mesh.matrix_world);mesh.matrix_world.identity();mesh.data.update()
mat=mesh.data.materials[0];pixels={}
for n in mat.node_tree.nodes:
    if n.type=='TEX_IMAGE' and n.image:
        values=np.empty(len(n.image.pixels),dtype=np.float32);n.image.pixels.foreach_get(values)
        pixels[n.image.name]=(values.reshape(n.image.size[1],n.image.size[0],4),n.image.size[:])
print('LINKS',[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in mat.node_tree.links])
uv=mesh.data.uv_layers.active
samples=[]
for point in [(0.186,.046,.36),(.16,-.06,.36),(.20,.12,.36),(0,.17,.5),(.13,-.08,.58)]:
    f=min(mesh.data.polygons,key=lambda f:(f.center-Vector(point)).length)
    co=sum((uv.data[i].uv for i in f.loop_indices),Vector((0,0)))/len(f.loop_indices)
    samples.append({'point':point,'face':list(f.center),'textures':{k:[round(float(v),4) for v in values[int(co.y*size[1])%size[1],int(co.x*size[0])%size[0],:3]] for k,(values,size) in pixels.items()}})
print('PBR_SAMPLES',json.dumps(samples),flush=True)
