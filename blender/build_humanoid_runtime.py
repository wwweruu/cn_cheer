"""Restore original PBR, retain a fixed complete pedestal, combine reviewed API clips."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import sys
import bmesh
import bpy
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[1]

def meshes():return [o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render]
def triangles(obj):return sum(len(p.vertices)-2 for p in obj.data.polygons)
def select(obj):
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj

def make_in_place(path):
    raw=path.read_bytes();length=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+length]);binary=bytearray(raw[28+length:])
    root=next(i for i,n in enumerate(doc['nodes']) if n.get('name')=='Hips');rest=doc['nodes'][root]['translation'];report={}
    for clip in doc['animations']:
        for channel in clip['channels']:
            if channel['target']!={'node':root,'path':'translation'}:continue
            accessor=doc['accessors'][clip['samplers'][channel['sampler']]['output']];view=doc['bufferViews'][accessor['bufferView']]
            assert accessor['componentType']==5126 and accessor['type']=='VEC3'
            offset=view.get('byteOffset',0)+accessor.get('byteOffset',0);stride=view.get('byteStride',12)
            values=[struct.unpack_from('<3f',binary,offset+i*stride) for i in range(accessor['count'])]
            report[clip['name']]={'original_x_range':[min(v[0] for v in values),max(v[0] for v in values)],'original_z_range':[min(v[2] for v in values),max(v[2] for v in values)]}
            for i,value in enumerate(values):struct.pack_into('<3f',binary,offset+i*stride,rest[0],value[1],rest[2])
            for key,func in (('min',min),('max',max)):
                if key in accessor:accessor[key]=[rest[0],func(v[1] for v in values),rest[2]]
    encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4)
    path.write_bytes(struct.pack('<4sII',b'glTF',2,28+len(encoded)+len(binary))+struct.pack('<I4s',len(encoded),b'JSON')+encoded+struct.pack('<I4s',len(binary),b'BIN\0')+binary)
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--piece',required=True);p.add_argument('--version',type=int,default=1);args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    folder=ROOT/'assets/generated/meshy'/args.piece;output=folder/f'motion/runtime/v{args.version}'
    assert not output.exists();output.mkdir(parents=True)
    input_version=2 if args.piece=='soldier_red' else 1
    info=json.loads((folder/f'rig-input/v{input_version}/input.json').read_text(encoding='utf8'));cut=info['base_cut']
    source=folder/f'runtime/v1/{args.piece}_desktop.glb';hashes={str(source.relative_to(ROOT)):hashlib.sha256(source.read_bytes()).hexdigest()}
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(source))
    static=meshes();assert len(static)==1;base=static[0]
    base.data.transform(base.matrix_world);base.parent=None;base.matrix_world=Matrix.Identity(4);base.name='OriginalFixedPedestal'
    material=base.data.materials[0];material.name=args.piece+'_original_PBR'
    bm=bmesh.new();bm.from_mesh(base.data);bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.co.z>=cut],context='VERTS')
    # Close only the exposed foot-contact holes at the top of the retained base.
    top_edges=[e for e in bm.edges if e.is_boundary and min(v.co.z for v in e.verts)>cut-.055]
    uv_layer=bm.loops.layers.uv.active;bm.normal_update()
    top_faces=[f for f in bm.faces if f.normal.z>.65 and cut-.10<f.calc_center_median().z<cut]
    top_samples=[(f.calc_center_median(),sum((loop[uv_layer].uv for loop in f.loops),start=f.loops[0][uv_layer].uv*0)/len(f.loops)) for f in top_faces]
    caps=bmesh.ops.holes_fill(bm,edges=top_edges,sides=0)['faces'] if top_edges else []
    for face in caps:
        cap_uv=min(top_samples,key=lambda sample:(sample[0]-face.calc_center_median()).length_squared)[1] if top_samples else None
        for loop in face.loops:
            if cap_uv is not None:loop[uv_layer].uv=cap_uv
        face.normal_update()
        if face.normal.z<0:face.normal_flip()
    cap_count=len(caps)
    if caps:bmesh.ops.triangulate(bm,faces=caps,quad_method='BEAUTY',ngon_method='BEAUTY')
    bm.to_mesh(base.data);bm.free();base.data.validate(clean_customdata=False);base.data.update()
    base_vertices=len(base.data.vertices);base_faces=triangles(base)
    actions={};armature=None;body=None
    for clip in ('idle','attack','hit','death','walk','run'):
        variant=2 if args.piece=='soldier_red' and clip=='death' else 1
        path=folder/f'motion/{clip}/v{variant}/model.glb' if clip not in ('walk','run') else folder/f'motion/rig/v1/{"walking" if clip=="walk" else "running"}.glb'
        hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
        before=set(bpy.data.objects);old_actions=set(bpy.data.actions);bpy.ops.import_scene.gltf(filepath=str(path))
        new_objects=set(bpy.data.objects)-before;new_actions=list(set(bpy.data.actions)-old_actions);assert len(new_actions)==1
        action=new_actions[0];action.name=clip;action.use_fake_user=True;actions[clip]=action
        if armature is None:
            armature=next(o for o in new_objects if o.type=='ARMATURE')
            body=next(o for o in new_objects if o.type=='MESH' and o.parent==armature)
        else:
            for obj in new_objects:bpy.data.objects.remove(obj,do_unlink=True)
    assert armature and body
    armature.animation_data_clear();armature.location.z+=cut;armature.data.pose_position='REST'
    body.data.materials.clear();body.data.materials.append(material)
    for polygon in body.data.polygons:polygon.material_index=0
    # The base-free API input can leave open soles. Close those tiny openings
    # with the adjacent boot UV and preserve their existing joint weights.
    bm=bmesh.new();bm.from_mesh(body.data);bm.normal_update();uv_layer=bm.loops.layers.uv.active
    bpy.context.view_layer.update();world=body.matrix_world.copy()
    bottom=min((world@v.co).z for v in bm.verts);edges=[e for e in bm.edges if e.is_boundary and max((world@v.co).z for v in e.verts)<bottom+.02]
    edge_uv={v:sum((l[uv_layer].uv for l in v.link_loops),start=v.link_loops[0][uv_layer].uv*0)/len(v.link_loops) for e in edges for v in e.verts if v.link_loops}
    sole_caps=bmesh.ops.holes_fill(bm,edges=edges,sides=0)['faces'] if edges else []
    for face in sole_caps:
        for loop in face.loops:
            if loop.vert in edge_uv:loop[uv_layer].uv=edge_uv[loop.vert]
        face.normal_update()
        if (world.to_3x3()@face.normal).z>0:face.normal_flip()
    if sole_caps:bmesh.ops.triangulate(bm,faces=sole_caps,quad_method='BEAUTY',ngon_method='BEAUTY')
    sole_count=len(sole_caps);bm.to_mesh(body.data);bm.free();body.data.validate(clean_customdata=False);body.data.update()
    # glTF needs an explicit joint for every vertex. A separate root bone keeps
    # the original pedestal fixed while the humanoid hips and limbs animate.
    select(armature);bpy.ops.object.mode_set(mode='EDIT');fixed=armature.data.edit_bones.new('FixedPedestal');fixed.head=(0,0,-cut/.01);fixed.tail=(0,0,-cut/.01+5);bpy.ops.object.mode_set(mode='OBJECT')
    base.vertex_groups.clear();group=base.vertex_groups.new(name='FixedPedestal');group.add(list(range(base_vertices)),1,'REPLACE')
    select(body);base.select_set(True);bpy.ops.object.join();body.name=args.piece+'_animated'
    armature.name=args.piece+'_rig';armature.data.pose_position='POSE'
    ad=armature.animation_data_create()
    clip_report={}
    for name,action in actions.items():
        track=ad.nla_tracks.new();track.name=name
        strip=track.strips.new(name,0,action);strip.action_slot=action.slots[0];strip.extrapolation='NOTHING'
        clip_report[name]={'frames':list(action.frame_range),'seconds':(action.frame_range[1]-action.frame_range[0])/bpy.context.scene.render.fps}
    ad.action=None
    for track in ad.nla_tracks:track.mute=True
    bpy.context.scene.frame_set(0);armature.data.pose_position='REST'
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(output/f'{args.piece}_animation_source.blend'),compress=True)
    report={'piece':args.piece,'api_rig':True,'original_pbr_restored':True,'base_cut':cut,'base_vertices_before_join':base_vertices,'base_triangles':base_faces,
        'fixed_base_bone':'FixedPedestal','closed_contact_holes':cap_count,'closed_sole_holes':sole_count,'clips':clip_report,'sources':hashes,'files':{}}
    # Every action uses the same rig. The exporter samples each NLA track alone.
    for tier,target,size in (('desktop',60000,4096),('mobile',20000,2048),('distant',12000,1024)):
        armature.data.pose_position='REST'
        if triangles(body)>target:
            select(body);modifier=body.modifiers.new('Runtime polygon budget','DECIMATE');modifier.ratio=(target-80)/triangles(body)
            bpy.ops.object.modifier_move_up(modifier=modifier.name)
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            body.data.validate(clean_customdata=False);body.data.update()
        used_images={node.image for node in material.node_tree.nodes if node.type=='TEX_IMAGE' and node.image}
        for image in used_images:
            if max(image.size)>size:image.scale(size,size)
        armature.data.pose_position='POSE'
        select(body);armature.select_set(True)
        path=output/f'{args.piece}_{tier}.glb'
        bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_yup=True,
            export_image_format='WEBP',export_image_quality=95,export_materials='EXPORT',export_animations=True,
            export_animation_mode='NLA_TRACKS',export_frame_range=False,export_force_sampling=True,
            export_skins=True,export_def_bones=False)
        root_motion=make_in_place(path)
        report['files'][tier]={'file':path.name,'triangles':triangles(body),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'removed_planar_root_motion':root_motion}
        print('ANIMATED_RUNTIME',args.piece,tier,report['files'][tier],flush=True)
    report['sources_unchanged']=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
    assert report['sources_unchanged']
    (output/'runtime.json').write_text(json.dumps(report,indent=2),encoding='utf8')

if __name__=='__main__':main()
