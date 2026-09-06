"""Repair reviewed API skins, rigid equipment, and original pedestal closures.

Creates immutable local derivatives; never changes the API or static masters.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, Quaternion
sys.path.insert(0, str(Path(__file__).parent))
from build_humanoid_runtime import make_in_place, triangles, select

ROOT=Path(__file__).resolve().parents[1]
TOPS={'soldier_black':.178,'soldier_red':.2067,'general_black':.194162,'general_red':.158,'advisor_red':.194,'advisor_black':.165}

def weapon(piece,co):
    x,y,z=co
    if piece=='soldier_black':
        if x<-.275 and z<.895:return 'RightHand'
        if x>.16 and z<.948:return 'LeftHand'
    if piece=='soldier_red':
        if x<-.285 and z<1.005:return 'RightHand'
        if z>.62 and z<1.145 and (x>.23 or (x>.15 and y<-.10)):return 'LeftHand'
    if piece=='general_black':
        if z<1.16 and math.hypot(x-(-.264-.038*z),y-(-.112+.068*z))<.031:return 'RightHand'
        if z>=1.16 and x<-.25 and -.08<y<.075:return 'RightHand'
    return None

def smooth(a,b,v):
    t=max(0,min(1,(v-a)/(b-a)));return t*t*(3-2*t)

def restrain_motion(rig,piece):
    """Reduce the exaggerated stock twist on the heavy black infantry armor."""
    ad=rig.animation_data;scene=bpy.context.scene
    for track in list(ad.nla_tracks):
        old=track.strips[0].action;name=track.name
        strengths={'idle':.32,'attack':.52,'hit':.65,'death':.85,'walk':.55,'run':.55} if piece=='soldier_black' else {'idle':.22,'attack':.28,'hit':.32,'death':.62,'walk':.30,'run':.30}
        strength=strengths[name]
        ad.action=old;ad.action_slot=old.slots[0];rig.data.pose_position='POSE';samples=[]
        for f in range(round(old.frame_range[0]),round(old.frame_range[1])+1):
            scene.frame_set(f);samples.append((f,[(p.name,p.location.copy(),p.rotation_quaternion.copy(),p.scale.copy()) for p in rig.pose.bones]))
        new=bpy.data.actions.new(name+'_reviewed');ad.action=new
        for f,values in samples:
            for bone,loc,rot,scale in values:
                bone_strength=.15 if piece=='soldier_black' and name=='death' and any(part in bone for part in ('Leg','Foot','Toe')) else strength
                p=rig.pose.bones[bone];p.rotation_mode='QUATERNION';p.location=loc*strength;p.rotation_quaternion=Quaternion().slerp(rot,bone_strength);p.scale=Vector((1,1,1)).lerp(scale,strength)
                for prop in ('location','rotation_quaternion','scale'):p.keyframe_insert(data_path=prop,frame=f,group=bone)
        ad.action=None;ad.nla_tracks.remove(track);track=ad.nla_tracks.new();track.name=name
        strip=track.strips.new(name,0,new);strip.action_slot=new.slots[0];strip.extrapolation='NOTHING';track.mute=True
    rig.data.pose_position='REST';scene.frame_set(0)

def lift_corpse_above_plate(rig,body,top):
    ad=rig.animation_data;scene=bpy.context.scene;action=next(t for t in ad.nla_tracks if t.name=='death').strips[0].action
    fixed=body.vertex_groups['FixedPedestal'].index
    indices=np.array([v.index for v in body.data.vertices if not any(g.group==fixed and g.weight>.999 for g in v.groups)])
    ad.action=action;ad.action_slot=action.slots[0];rig.data.pose_position='POSE';hip=rig.pose.bones['Hips']
    delta_axis=(rig.matrix_world@hip.bone.matrix_local).to_3x3().inverted()@Vector((0,0,1));peak=0
    for frame in range(round(action.frame_range[0]),round(action.frame_range[1])+1):
        scene.frame_set(frame);bpy.context.view_layer.update();evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        data=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',data);coords=data.reshape(-1,3)[indices];matrix=np.array(body.matrix_world)
        coords=coords@matrix[:3,:3].T+matrix[:3,3];inside=(coords[:,0]**2+coords[:,1]**2)<.35**2
        lift=max(0,top+.004-float(coords[inside,2].min())) if inside.any() else 0;evaluated.to_mesh_clear()
        if lift>0:hip.location+=delta_axis*lift;hip.keyframe_insert(data_path='location',frame=frame,group='Hips');peak=max(peak,lift)
    ad.action=None;rig.data.pose_position='REST';scene.frame_set(0);return peak

def split_at(obj,z,keep_top,cap_uv):
    bm=bmesh.new();bm.from_mesh(obj.data);uv=bm.loops.layers.uv.active
    cut=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.000001,
        plane_co=(0,0,z),plane_no=(0,0,1),clear_inner=keep_top,clear_outer=not keep_top)
    edges=[e for e in cut['geom_cut'] if isinstance(e,bmesh.types.BMEdge) and e.is_boundary]
    caps=bmesh.ops.holes_fill(bm,edges=edges,sides=0)['faces'] if edges else []
    for f in caps:
        for l in f.loops:l[uv].uv=cap_uv+Vector((l.vert.co.x*.001,l.vert.co.y*.001))
        f.normal_update()
        if (f.normal.z>0)==keep_top:f.normal_flip()
    if caps:bmesh.ops.triangulate(bm,faces=caps)
    bm.to_mesh(obj.data);bm.free();obj.data.validate(clean_customdata=False);obj.data.update()
    return len(caps)

def main():
    p=argparse.ArgumentParser();p.add_argument('--piece',required=True);p.add_argument('--version',type=int,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);piece=args.piece
    folder=ROOT/'assets/generated/meshy'/piece;out=folder/f'motion/runtime/v{args.version}';assert not out.exists();out.mkdir(parents=True)
    previous=5 if piece=='soldier_red' else 1
    old=folder/f'motion/runtime/v{previous}/{piece}_animation_source.blend'
    original=folder/f'runtime/v1/{piece}_desktop.glb'
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (old,original)}
    bpy.ops.wm.open_mainfile(filepath=str(old));rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    rig.data.pose_position='REST';bpy.context.view_layer.update();oldmesh=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.parent==rig)
    names={g.index:g.name for g in oldmesh.vertex_groups}
    oldmesh.data.transform(oldmesh.matrix_world);oldmesh.parent=None;oldmesh.matrix_world=Matrix.Identity(4);oldmesh.modifiers.clear()
    bm=bmesh.new();bm.from_mesh(oldmesh.data);deform=bm.verts.layers.deform.active
    fixed_index=oldmesh.vertex_groups['FixedPedestal'].index
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if v[deform].get(fixed_index,0)>.999],context='VERTS')
    bm.to_mesh(oldmesh.data);bm.free();body=oldmesh
    before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(original));base=next(o for o in set(bpy.data.objects)-before if o.type=='MESH')
    base.data.transform(base.matrix_world);base.parent=None;base.matrix_world=Matrix.Identity(4);base.data.update()
    material=base.data.materials[0];uv_layer=base.data.uv_layers.active;top=TOPS[piece]
    # Pick a real unobstructed top sample near the edge of the original plate.
    candidates=[f for f in base.data.polygons if f.normal.z>.9 and top-.009<f.center.z<top+.004 and .20<math.hypot(f.center.x,f.center.y)<.31]
    sample=max(candidates,key=lambda f:f.area)
    cap_uv=sum((uv_layer.data[i].uv for i in sample.loop_indices),Vector((0,0)))/len(sample.loop_indices)
    base_caps=split_at(base,top-.002,False,cap_uv)
    # Scans can have existing open boundaries: an explicit flat plate closes the
    # entire exposed top independently of the scan's boundary topology.
    edge=[v.co for v in base.data.vertices if v.co.z>top-.006]
    rx=max(abs(v.x) for v in edge)*.967;ry=max(abs(v.y) for v in edge)*.967
    bm=bmesh.new();bm.from_mesh(base.data);uv=bm.loops.layers.uv.active
    center=bm.verts.new((0,0,top-.0017))
    rim=[bm.verts.new((rx*math.cos(i*math.tau/128),ry*math.sin(i*math.tau/128),top-.0017)) for i in range(128)]
    for i in range(128):
        f=bm.faces.new((center,rim[i],rim[(i+1)%128]))
        for l in f.loops:l[uv].uv=cap_uv+Vector((l.vert.co.x*.015,l.vert.co.y*.015))
    bm.to_mesh(base.data);bm.free();base.data.update()
    body_caps=0
    base.vertex_groups.clear();base.vertex_groups.new(name='FixedPedestal').add(list(range(len(base.data.vertices))),1,'REPLACE')
    groups={g.name:g for g in body.vertex_groups}
    rigid_counts=Counter();distances=[0]
    for v in body.data.vertices:
        bone=weapon(piece,v.co)
        x,y,z=v.co
        if not bone and piece in ('soldier_black','advisor_red'):
            amount=1-smooth(.80,1.0,z) if piece=='soldier_black' else 1-smooth(.83,1.1,z)
            if amount>0:
                ws={names[g.group]:g.weight*(1-amount) for g in v.groups};ws['Hips']=ws.get('Hips',0)+amount
                for g in body.vertex_groups:g.remove([v.index])
                for name,w in ws.items():
                    if w>1e-7:groups[name].add([v.index],w,'REPLACE')
        if bone:
            for g in body.vertex_groups:g.remove([v.index])
            groups[bone].add([v.index],1,'REPLACE');rigid_counts[bone]+=1
    body.data.materials.clear();body.data.materials.append(material)
    for f in body.data.polygons:f.material_index=0
    if piece=='soldier_black':
        bm=bmesh.new();bm.from_mesh(body.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001);deform=bm.verts.layers.deform.active
        feet={g.index for g in body.vertex_groups if 'Foot' in g.name or 'Toe' in g.name}
        edges=[e for e in bm.edges if e.is_boundary and max(v.co.z for v in e.verts)<.28 and all(sum(v[deform].get(i,0) for i in feet)>.4 for v in e.verts)]
        uv=bm.loops.layers.uv.active;boot_uv=cap_uv
        caps=bmesh.ops.holes_fill(bm,edges=edges,sides=0)['faces'] if edges else []
        for f in caps:
            f.smooth=False;f.normal_update()
            if f.normal.z>0:f.normal_flip()
            for l in f.loops:l[uv].uv=boot_uv+Vector((l.vert.co.x*.001,l.vert.co.y*.001))
        if caps:bmesh.ops.triangulate(bm,faces=caps)
        body_caps=len(caps);bm.to_mesh(body.data);bm.free();body.data.validate(clean_customdata=False);body.data.update()
    if piece=='general_black':
        # The scanned pole touches the boot and banner touches the shoulder.
        # Open those artificial bridges so rigid equipment can move freely.
        bm=bmesh.new();bm.from_mesh(body.data)
        bridges=[]
        for f in bm.faces:
            flags=[bool(weapon(piece,v.co)) for v in f.verts]
            if any(flags) and not all(flags) and (max(v.co.z for v in f.verts)<.35 or min(v.co.z for v in f.verts)>1.10):bridges.append(f)
        bmesh.ops.delete(bm,geom=bridges,context='FACES');bm.to_mesh(body.data);bm.free();body.data.update()
    # Join in world coordinates before applying the rig's inverse bind transform.
    select(body);base.select_set(True);bpy.ops.object.join()
    body.data.transform(rig.matrix_world.inverted());body.parent=rig;body.matrix_parent_inverse=Matrix.Identity(4);body.matrix_basis=Matrix.Identity(4)
    modifier=body.modifiers.new('Reviewed humanoid skin','ARMATURE');modifier.object=rig;body.name=piece+'_animated'
    bpy.context.view_layer.update()
    for track in rig.animation_data.nla_tracks:track.mute=True
    if piece in ('soldier_black','advisor_red'):restrain_motion(rig,piece)
    corpse_lift=lift_corpse_above_plate(rig,body,top) if piece=='soldier_black' else 0
    bpy.context.scene.frame_set(0);rig.data.pose_position='REST'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/f'{piece}_animation_source.blend'),compress=True)
    report={'piece':piece,'api_rig':True,'api_cost':0,'method':'reviewed API skin with rigid hand-held equipment, smoothed garment weights, restrained heavy-clothing motion, planar original pedestal closure',
        'fixed_base_bone':'FixedPedestal','base_surface':top,'base_caps':base_caps,'sole_caps':body_caps,'rigid_vertices':dict(rigid_counts),'corpse_peak_lift':corpse_lift,
        'transfer_distance':{'mean':sum(distances)/len(distances),'max':max(distances)},'sources':sources,'clips':{},'files':{}}
    for track in rig.animation_data.nla_tracks:
        action=track.strips[0].action;report['clips'][track.name]={'frames':list(action.frame_range),'seconds':(action.frame_range[1]-action.frame_range[0])/bpy.context.scene.render.fps}
    for tier,target,size in (('desktop',60000,4096),('mobile',20000,2048),('distant',12000,1024)):
        rig.data.pose_position='REST'
        if triangles(body)>target:
            select(body);dec=body.modifiers.new('Runtime polygon budget','DECIMATE');dec.ratio=(target-80)/triangles(body);bpy.ops.object.modifier_move_up(modifier=dec.name);bpy.ops.object.modifier_apply(modifier=dec.name);body.data.validate(clean_customdata=False);body.data.update()
        for im in {n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image}:
            if max(im.size)>size:im.scale(size,size)
        rig.data.pose_position='POSE';select(body);rig.select_set(True);path=out/f'{piece}_{tier}.glb'
        bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_yup=True,export_image_format='WEBP',export_image_quality=95,export_materials='EXPORT',export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_force_sampling=True,export_skins=True,export_def_bones=False)
        roots=make_in_place(path);report['files'][tier]={'file':path.name,'triangles':triangles(body),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'removed_planar_root_motion':roots}
        print('REPAIRED',piece,tier,report['files'][tier]['triangles'],flush=True)
    report['sources_unchanged']=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in sources.items());assert report['sources_unchanged']
    (out/'runtime.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('BINDING_REPORT',report['rigid_vertices'],report['transfer_distance'],flush=True)

if __name__=='__main__':main()
