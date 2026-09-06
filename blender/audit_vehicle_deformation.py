import bpy, sys, json, math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
piece,version=sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/generated/meshy'/piece/f'motion/runtime/v{version}/{piece}_animation_source.blend'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
rig.data.pose_position='POSE'
track=next(t for t in rig.animation_data.nla_tracks if t.name=='attack')
rig.animation_data.action=track.strips[0].action;rig.animation_data.action_slot=track.strips[0].action.slots[0]
bpy.context.scene.frame_set(24)
bpy.context.view_layer.update()
eval_obj=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());posed=eval_obj.to_mesh()
bad=[]
for face in mesh.data.polygons:
    ids=list(face.vertices)
    ratio=max(((posed.vertices[a].co-posed.vertices[b].co).length/max(.0001,(mesh.data.vertices[a].co-mesh.data.vertices[b].co).length) for a,b in zip(ids,ids[1:]+ids[:1])))
    if ratio>4:
        bad.append((ratio, list(face.center), [[mesh.vertex_groups[g.group].name,round(g.weight,3)] for i in ids for g in mesh.data.vertices[i].groups]))
bad.sort(reverse=True)
print('BAD_TRIANGLES',len(bad),json.dumps(bad[:25]),flush=True)
