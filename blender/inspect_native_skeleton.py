"""Sample actual imported skeletons for diagnosing retarget alignment."""
import argparse,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
bpy.ops.wm.read_factory_settings(use_empty=True)
source=ROOT/a.input
if source.suffix=='.fbx':bpy.ops.import_scene.fbx(filepath=str(source))
else:bpy.ops.import_scene.gltf(filepath=str(source))
result={'objects':[(o.name,o.type,o.hide_render,list(o.scale)) for o in bpy.context.scene.objects], 'rigs':[]}
for rig in [o for o in bpy.context.scene.objects if o.type=='ARMATURE']:
 ad=rig.animation_data
 actions=[ad.action] if ad and ad.action else []
 if ad:
  actions+= [t.strips[0].action for t in ad.nla_tracks if t.strips]
  for t in ad.nla_tracks:t.mute=True
 record={'name':rig.name,'matrix':[list(row) for row in rig.matrix_world],'bones':{b.name:{'parent':b.parent.name if b.parent else None,'rest':list(rig.matrix_world@b.head_local)} for b in rig.data.bones},'actions':[]}
 for action in dict.fromkeys(actions):
  ad.action=action;ad.action_slot=action.slots[0]
  frames=[round(action.frame_range[0]+(action.frame_range[1]-action.frame_range[0])*i/8) for i in range(9)]
  sampled=[]
  for f in frames:
   bpy.context.scene.frame_set(f);bpy.context.view_layer.update()
   sampled.append({'frame':f,'joints':{b.name:list(rig.matrix_world@b.head) for b in rig.pose.bones}})
  record['actions'].append({'name':action.name,'frames':list(action.frame_range),'samples':sampled})
 result['rigs'].append(record)
out=ROOT/a.output;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2));print('SKELETON_SAMPLED',out,[(r['name'],len(r['bones'])) for r in result['rigs']],flush=True)
