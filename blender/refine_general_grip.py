"""Fit the black general's authored open hand to its staff without regenerating art."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).parent))
from build_humanoid_runtime import select,triangles
from build_native_humanoid import curve_bags, equipment
from contact_kinematics import solve_chain, smooth


def main():
    p=argparse.ArgumentParser();p.add_argument('--previous',type=int,required=True);p.add_argument('--version',type=int,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);piece='general_black'
    folder=ROOT/'assets/generated/meshy'/piece;previous=folder/f'motion/runtime/v{a.previous}';out=folder/f'motion/runtime/v{a.version}'
    assert not out.exists(),out
    out.mkdir(parents=True)
    source=previous/f'{piece}_animation_source.blend';report=json.loads((previous/'runtime.json').read_text(encoding='utf-8'))
    report['sources'][str(source.relative_to(ROOT))]=hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    body=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.find_armature()==rig)
    rig.data.pose_position='REST';bpy.context.view_layer.update()
    world=rig.matrix_world;inv=world.inverted()
    wrist=world@rig.data.bones['RightHand'].head_local
    original_hand=[v for v in body.data.vertices if (world@v.co).x<-.363 and (world@v.co).y<-.145 and .90<(world@v.co).z<1.04]
    assert len(original_hand)>30,len(original_hand)
    mean=sum((world@v.co for v in original_hand),Vector())/len(original_hand)
    direction=(mean-wrist).normalized()
    # The generated hand points down and forward. Curl its distal surface
    # around the existing palm plane, then orient that grip around the shaft.
    cloud=np.array([list(world@v.co) for v in original_hand])
    _,vectors=np.linalg.eigh(np.cov(cloud.T))
    normal=Vector(vectors[:,0]);normal=(normal-direction*normal.dot(direction)).normalized()
    if normal.dot(Vector((1,1,0)))<0:normal.negate()
    width=normal.cross(direction).normalized();normal=direction.cross(width).normalized()
    source_axes=Matrix((direction,width,normal)).transposed()
    desired_axes=Matrix((Vector((0,-1,0)),Vector((0,0,-1)),Vector((1,0,0)))).transposed()
    rotation=desired_axes@source_axes.transposed()
    knuckle=.039;radius=.018
    hand_indices=[]
    for v in body.data.vertices:
        co=world@v.co;delta=co-wrist;along=delta.dot(direction)
        if co.x<-.34 and co.y<-.13 and .89<co.z<1.065 and not equipment(piece,co):
            influence=smooth(.012,.031,along)
            if along>knuckle:
                theta=min(2.35,(along-knuckle)/radius)
                co+=direction*(radius*math.sin(theta)-(along-knuckle))+normal*(radius*(1-math.cos(theta)))
                v.co=inv@co
            if influence>0:
                old={g.group:g.weight*(1-influence) for g in v.groups}
                for group in body.vertex_groups:group.remove([v.index])
                old[body.vertex_groups['RightHand'].index]=old.get(body.vertex_groups['RightHand'].index,0)+influence
                for index,value in old.items():
                    if value>1e-7:body.vertex_groups[index].add([v.index],value,'REPLACE')
                hand_indices.append(v.index)
    # Keep the pole a rigid independent part. Its grip target drives the arm.
    grip=Vector((-.304,-.043,1.075))
    select(rig);bpy.ops.object.mode_set(mode='EDIT')
    bone=rig.data.edit_bones.new('HeldWeapon');bone.head=inv@grip;bone.tail=bone.head+Vector((0,0,10));bone.parent=rig.data.edit_bones['Hips']
    bpy.ops.object.mode_set(mode='OBJECT')
    group=body.vertex_groups.new(name='HeldWeapon')
    indices=set()
    attribute=body.data.attributes.get('native_equipment')
    for f in body.data.polygons:
        if attribute and attribute.data[f.index].value==1:
            indices.update(f.vertices)
    assert len(indices)>500,len(indices)
    for index in indices:
        for g in body.vertex_groups:g.remove([index])
        group.add([index],1,'REPLACE')
    body.data.update()
    palm_offset=direction*knuckle+normal*radius
    local_rotation=(inv.to_3x3()@rotation@world.to_3x3()).to_quaternion()
    hand_orientation=(local_rotation@rig.data.bones['RightHand'].matrix_local.to_quaternion()).normalized()
    ad=rig.animation_data;actions={t.name:t.strips[0].action for t in ad.nla_tracks if t.strips}
    for track in list(ad.nla_tracks):ad.nla_tracks.remove(track)
    rig.data.pose_position='POSE';errors={}
    for name,old in actions.items():
        ad.action=old;ad.action_slot=old.slots[0];first,last=old.frame_range;samples=[];peak=0
        for frame in range(round(first),round(last)+1):
            bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
            pole=rig.pose.bones['HeldWeapon'];m=pole.bone.matrix_local.copy()
            if name in ('idle','walk','run'):
                # The staff is upright and raised slightly during locomotion.
                m.translation+=inv.to_3x3()@Vector((0,0,.020 if name in ('walk','run') else .004))
            else:
                hand=rig.pose.bones['RightHand'];m=hand.matrix@hand.bone.matrix_local.inverted()@m
            pole.matrix=m;bpy.context.view_layer.update()
            grip_world=world@pole.head
            target_world=grip_world-rotation@palm_offset
            target=inv@target_world
            peak=max(peak,solve_chain(rig,'RightArm','RightForeArm','RightHand',target,inv@Vector((-.42,.09,1.16)),hand_orientation))
            samples.append({b.name:(b.location.copy(),b.rotation_quaternion.copy(),b.scale.copy()) for b in rig.pose.bones})
        if name in ('idle','walk','run') and not report['clips'][name].get('loop_closed'):
            for index in range(max(1,len(samples)-6),len(samples)):
                t=smooth(len(samples)-7,len(samples)-1,index)
                for bone,(loc,rot,scale) in list(samples[index].items()):
                    x,y,z=samples[0][bone];samples[index][bone]=(loc.lerp(x,t),rot.slerp(y,t),scale.lerp(z,t))
            samples[-1]=samples[0]
        elif name in ('idle','walk','run'):
            samples[-1]=samples[0]
        result=bpy.data.actions.new(name+'_grip');ad.action=result
        for frame,pose in enumerate(samples):
            for bone,(loc,rot,scale) in pose.items():
                pb=rig.pose.bones[bone];pb.rotation_mode='QUATERNION';pb.location=loc;pb.rotation_quaternion=rot;pb.scale=scale
                for prop in ('location','rotation_quaternion','scale'):pb.keyframe_insert(data_path=prop,frame=frame,group=bone)
        for bag in curve_bags(result):
            for curve in bag.fcurves:
                for key in curve.keyframe_points:key.interpolation='LINEAR'
        ad.action=None;track=ad.nla_tracks.new();track.name=name;strip=track.strips.new(name,0,result);strip.action_slot=result.slots[0];strip.extrapolation='NOTHING';track.mute=True
        errors[name]=peak*.01
    report['grip_refinement']={'method':'local finger curl, independent rigid staff and two-segment arm IK','hand_vertices':len(hand_indices),'weapon_vertices':len(indices),'hand_target_error_m':errors}
    report['files']={};rig.data.pose_position='REST';bpy.context.scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/f'{piece}_animation_source.blend'),compress=True)
    if triangles(body)>20000:
        select(body);dec=body.modifiers.new('Runtime budget','DECIMATE');dec.ratio=19900/triangles(body);bpy.ops.object.modifier_move_up(modifier=dec.name);bpy.ops.object.modifier_apply(modifier=dec.name)
    body.data.validate(clean_customdata=False);body.data.update()
    for image in {n.image for mat in body.data.materials for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image}:
        if max(image.size)>2048:image.scale(2048,2048)
    rig.data.pose_position='POSE';select(body);rig.select_set(True);path=out/f'{piece}_mobile.glb'
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_yup=True,export_image_format='WEBP',export_image_quality=95,export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_force_sampling=True,export_skins=True,export_def_bones=False)
    report['files']['mobile']={'file':path.name,'triangles':triangles(body),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    report['sources_unchanged']=all(hashlib.sha256((ROOT/k).read_bytes()).hexdigest()==v for k,v in report['sources'].items());assert report['sources_unchanged']
    (out/'runtime.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('GENERAL_GRIP',report['grip_refinement'],flush=True)


if __name__=='__main__':main()
