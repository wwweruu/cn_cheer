"""Editable local rigs for the eight mounted/animal/mechanical pieces; no API cost."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[1]
def smooth(a,b,v):
    t=max(0,min(1,(v-a)/(b-a)));return t*t*(3-2*t)
def select(obj):
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
def tris(obj):return sum(len(p.vertices)-2 for p in obj.data.polygons)

def main():
    p=argparse.ArgumentParser();p.add_argument('--piece',required=True);p.add_argument('--version',type=int,default=1);args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    family,camp=args.piece.split('_');assert family in ('horse','elephant','chariot','cannon')
    folder=ROOT/'assets/generated/meshy'/args.piece;out=folder/f'motion/runtime/v{args.version}';assert not out.exists();out.mkdir(parents=True)
    source=folder/f'runtime/v1/{args.piece}_desktop.glb';digest=hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(source))
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH');mesh.data.transform(mesh.matrix_world);mesh.parent=None;mesh.matrix_world=Matrix.Identity(4)
    height=max(v.co.z for v in mesh.data.vertices);base=height*(.115 if family=='cannon' else .10)
    # Native glTF +Z front becomes Blender -Y. Keep every vertex of the source.
    rig_data=bpy.data.armatures.new(args.piece+'_rig');rig=bpy.data.objects.new(args.piece+'_rig',rig_data);bpy.context.collection.objects.link(rig)
    select(rig);bpy.ops.object.mode_set(mode='EDIT')
    bone_defs={'FixedPedestal':(0,0,0),'Body':(0,0,base),
      'Detail':(0,-.14,height*(.61 if family=='cannon' else .45)), 'Accents':(0,0,height*.73)}
    for name,head in bone_defs.items():
        b=rig_data.edit_bones.new(name);b.head=head;b.tail=(head[0],head[1],head[2]+.1)
        if name!='FixedPedestal':b.parent=rig_data.edit_bones['FixedPedestal' if name=='Body' else 'Body']
    bpy.ops.object.mode_set(mode='OBJECT')
    groups={name:mesh.vertex_groups.new(name=name) for name in bone_defs}
    for v in mesh.data.vertices:
        x,y,z=v.co;body=smooth(base,base+height*.13,z)
        if family=='cannon' and camp=='black':detail=smooth(height*.58,height*.65,z)
        elif family=='cannon':detail=smooth(0,.12,x)*smooth(height*.4,height*.6,z)
        else:detail=smooth(.06,.28,-y)*smooth(height*.25,height*.43,z)*(1-smooth(height*.63,height*.73,z))
        accent=smooth(height*.73,height*.90,z)*(1-detail)
        weights={'FixedPedestal':1-body,'Body':body*(1-detail)*(1-accent),'Detail':body*detail,'Accents':body*(1-detail)*accent}
        total=sum(weights.values())
        for name,w in weights.items():
            if w>0:groups[name].add([v.index],w/total,'REPLACE')
    modifier=mesh.modifiers.new('Part articulation','ARMATURE');modifier.object=rig;mesh.parent=rig
    mesh.name=args.piece+'_animated';scene=bpy.context.scene;scene.render.fps=30
    clips={};ad=rig.animation_data_create()
    for name,duration in (('idle',4),('attack',1.5),('hit',.7),('death',1.6),('walk',1.2),('run',.8)):
        action=bpy.data.actions.new(name);ad.action=action
        for frame in range(round(duration*30)+1):
            t=frame/30;p=t/duration;s=math.sin(2*math.pi*p)
            for bone in rig.pose.bones:bone.rotation_mode='XYZ';bone.location=(0,0,0);bone.rotation_euler=(0,0,0);bone.scale=(1,1,1)
            body=rig.pose.bones['Body'];detail=rig.pose.bones['Detail'];accents=rig.pose.bones['Accents']
            if name=='idle':
                body.scale.y=1+.0025*s;detail.rotation_euler.x=.018*s;accents.rotation_euler.y=.012*math.sin(2*math.pi*p+.4)
            elif name in ('walk','run'):
                body.location.y=.009*(1-math.cos(4*math.pi*p));body.rotation_euler.x=.014*s
                detail.rotation_euler.x=.028*s;accents.rotation_euler.y=.019*s
            elif name=='attack':
                anticipation=math.sin(math.pi*min(1,p/.35)) if p<.35 else 0
                strike=math.sin(math.pi*min(1,max(0,(p-.35)/.4)))
                if family=='cannon' and camp=='black':detail.rotation_euler.x=-.40*anticipation+.95*strike;body.rotation_euler.x=-.02*strike
                elif family=='cannon':detail.location.z=.04*strike;detail.rotation_euler.x=-.035*strike;body.rotation_euler.x=-.025*strike
                else:body.rotation_euler.x=.08*strike-.025*anticipation;detail.rotation_euler.x=.12*strike;accents.rotation_euler.x=.04*strike
            elif name=='hit':
                pulse=math.sin(math.pi*p)*(1-p);body.rotation_euler.x=-.15*pulse;body.rotation_euler.y=.04*math.sin(4*math.pi*p)*(1-p)
            elif name=='death':
                slump=smooth(0,.8,p);body.rotation_euler.x=-.14*slump;body.rotation_euler.y=.10*slump;body.scale.y=1-.10*slump;detail.rotation_euler.x=.16*slump;accents.rotation_euler.x=-.13*slump
            for bone in rig.pose.bones:
                for prop in ('location','rotation_euler','scale'):bone.keyframe_insert(data_path=prop,frame=frame,group=bone.name)
        action=ad.action;action.use_fake_user=True;track=ad.nla_tracks.new();track.name=name
        strip=track.strips.new(name,0,action);strip.action_slot=action.slots[0];strip.extrapolation='NOTHING';track.mute=True
        clips[name]={'seconds':duration,'frames':[0,round(duration*30)]};ad.action=None
    for bone in rig.pose.bones:bone.location=(0,0,0);bone.rotation_euler=(0,0,0);bone.scale=(1,1,1)
    scene.frame_set(0);rig.data.pose_position='REST'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/f'{args.piece}_animation_source.blend'),compress=True)
    report={'piece':args.piece,'api_rig':False,'method':'local weighted part articulation','api_cost':0,'fixed_base_bone':'FixedPedestal','fixed_below':base,'clips':clips,'sources':{str(source.relative_to(ROOT)):digest},'files':{}}
    for tier,target,size in (('desktop',60000,4096),('mobile',20000,2048),('distant',12000,1024)):
        rig.data.pose_position='REST'
        if tris(mesh)>target:
            select(mesh);dec=mesh.modifiers.new('Runtime budget','DECIMATE');dec.ratio=(target-80)/tris(mesh);bpy.ops.object.modifier_move_up(modifier=dec.name);bpy.ops.object.modifier_apply(modifier=dec.name);mesh.data.validate(clean_customdata=False)
        for mat in mesh.data.materials:
            for image in {n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image}:
                if max(image.size)>size:image.scale(size,size)
        rig.data.pose_position='POSE';select(mesh);rig.select_set(True);path=out/f'{args.piece}_{tier}.glb'
        bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_yup=True,export_image_format='WEBP',export_image_quality=95,export_materials='EXPORT',export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_force_sampling=True,export_skins=True,export_def_bones=False)
        report['files'][tier]={'file':path.name,'triangles':tris(mesh),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        print('LOCAL_MOTION',args.piece,tier,report['files'][tier],flush=True)
    report['sources_unchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==digest;assert report['sources_unchanged']
    (out/'runtime.json').write_text(json.dumps(report,indent=2),encoding='utf8')

if __name__=='__main__':main()
