"""Read-only rest skeleton and skin-region diagnostics for native candidates."""
import json
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]
piece, version = sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/generated/meshy'/piece/f'motion/runtime/v{version}/{piece}_animation_source.blend'))
rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH' and o.find_armature() == rig)
rig.data.pose_position = 'REST'
bpy.context.view_layer.update()
result = {'piece': piece, 'matrix': [list(row) for row in rig.matrix_world], 'bones': {}, 'regions': {}}
for b in rig.data.bones:
    result['bones'][b.name] = {'head':list(rig.matrix_world@b.head_local),'tail':list(rig.matrix_world@b.tail_local),'parent':b.parent.name if b.parent else None}
for g in mesh.vertex_groups:
    points = [mesh.matrix_world@v.co for v in mesh.data.vertices if any(w.group == g.index and w.weight > .5 for w in v.groups)]
    if points:
        result['regions'][g.name] = {'count':len(points),'bounds':[[min(v[i] for v in points),max(v[i] for v in points)] for i in range(3)]}
out = ROOT/'.meshy/native-refine'
out.mkdir(parents=True, exist_ok=True)
(out/f'{piece}-v{version}-rest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('CONTACT_REST',piece,json.dumps(result['bones']),flush=True)
