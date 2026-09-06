"""Measure exported GLB foot surfaces, pedestal drift and loop seams."""
import argparse
import json
import math
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
GROUND={'soldier_red':.2065,'soldier_black':.1768,'general_black':.19296,'advisor_red':.1928,'horse_red':.1168,'horse_black':.0768,'elephant_red':.1548,'elephant_black':.1108,'cannon_red':.1728,'cannon_black':.1208}


def points(mesh):
    obj=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());data=obj.to_mesh()
    values=np.empty(len(data.vertices)*3,dtype=np.float32);data.vertices.foreach_get('co',values)
    coords=values.reshape(-1,3);world=np.asarray(obj.matrix_world);coords=coords@world[:3,:3].T+world[:3,3]
    obj.to_mesh_clear();return coords


def main():
    p=argparse.ArgumentParser();p.add_argument('--piece',required=True);p.add_argument('--version',type=int,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);piece=a.piece
    folder=ROOT/'assets/generated/meshy'/piece/f'motion/runtime/v{a.version}'
    report=json.loads((folder/'runtime.json').read_text(encoding='utf-8'))
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(folder/f'{piece}_mobile.glb'))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.find_armature()==rig)
    rig.data.pose_position='REST';bpy.context.view_layer.update();rest=points(mesh)
    names={g.index:g.name for g in mesh.vertex_groups};fixed=[];feet={}
    for v in mesh.data.vertices:
        for w in v.groups:
            name=names[w.group]
            if w.weight<.96:continue
            if name=='FixedPedestal':fixed.append(v.index)
            if name.endswith('Foot') and not name.startswith(('Rider','Native')):feet.setdefault(name,[]).append(v.index)
    for name,indices in list(feet.items()):
        minimum=min(rest[indices,2]);feet[name]=[i for i in indices if rest[i,2]<minimum+.004]
    edge_ids=np.array([list(e.vertices) for e in mesh.data.edges],dtype=np.int32)
    lengths=np.linalg.norm(rest[edge_ids[:,0]]-rest[edge_ids[:,1]],axis=1)
    ankle_max=.44 if piece=='soldier_black' else .47
    ankle_mask=(lengths>.002)&(rest[edge_ids].min(axis=1)[:,2]>GROUND[piece]+.025)&(rest[edge_ids].max(axis=1)[:,2]<ankle_max)
    ankle_edges=edge_ids[ankle_mask];ankle_lengths=lengths[ankle_mask]
    ad=rig.animation_data;actions=([ad.action] if ad.action else [])+[t.strips[0].action for t in ad.nla_tracks if t.strips]
    for track in ad.nla_tracks:track.mute=True
    allowed=report.get('review_clips') or [n for n,i in report.get('clip_sources',{}).items() if i['text_to_motion']]
    if not allowed:allowed=['idle']
    rows=[];rig.data.pose_position='POSE'
    for action in dict.fromkeys(actions):
        name=action.name.split('_contacts')[0].split('_grip')[0]
        if name not in allowed:continue
        ad.action=action;ad.action_slot=action.slots[0];start,end=action.frame_range
        row={'clip':name,'frames':list(action.frame_range),'feet':{},'pedestal_drift_m':0,'ankle_edge_stretch_p99':1,'ankle_edge_stretch_max':1}
        first_pose=last_pose=None
        for index in range(41):
            progress=index/40;f=start+(end-start)*progress
            bpy.context.scene.frame_set(math.floor(f),subframe=f%1);bpy.context.view_layer.update();co=points(mesh)
            if index==0:first_pose=co.copy()
            if index==40:last_pose=co.copy()
            if fixed:row['pedestal_drift_m']=max(row['pedestal_drift_m'],float(np.linalg.norm(co[fixed]-rest[fixed],axis=1).max()))
            if len(ankle_edges):
                stretch=np.linalg.norm(co[ankle_edges[:,0]]-co[ankle_edges[:,1]],axis=1)/ankle_lengths
                row['ankle_edge_stretch_p99']=max(row['ankle_edge_stretch_p99'],float(np.percentile(stretch,99)))
                if float(stretch.max())>row['ankle_edge_stretch_max']:
                    worst=int(stretch.argmax());ids=ankle_edges[worst]
                    row['worst_ankle_edge']={'rest':[list(map(float,rest[i])) for i in ids],'weights':[{names[w.group]:w.weight for w in mesh.data.vertices[i].groups} for i in ids]}
                    row['ankle_edge_stretch_max']=float(stretch.max())
            for foot,indices in feet.items():
                height=float(co[indices,2].min()-GROUND[piece])
                data=row['feet'].setdefault(foot,{'vertices':len(indices),'min_surface_clearance_m':1,'max_surface_clearance_m':-1,'support_error_max_m':0})
                data['min_surface_clearance_m']=min(data['min_surface_clearance_m'],height)
                data['max_surface_clearance_m']=max(data['max_surface_clearance_m'],height)
                if foot.startswith('Elephant') and name=='walk':
                    part=foot[len('Elephant'):len('Elephant')+2];phase={'RL':0,'FL':.25,'RR':.5,'FR':.75}[part]
                    if (progress+phase)%1<.76:data['support_error_max_m']=max(data['support_error_max_m'],abs(height))
        row['loop_vertex_jump_m']=float(np.linalg.norm(last_pose-first_pose,axis=1).max())
        rows.append(row)
    result={'piece':piece,'version':a.version,'file':str((folder/f'{piece}_mobile.glb').relative_to(ROOT)),'clips':rows}
    out=ROOT/'docs/asset-reports/native-motion/refinement';out.mkdir(parents=True,exist_ok=True)
    (out/f'{piece}-v{a.version}-contacts.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('GLB_CONTACT_AUDIT',json.dumps(result),flush=True)


if __name__=='__main__':main()
