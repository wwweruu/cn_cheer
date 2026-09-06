"""Attach Meshy's native human rig and generated performance to original mounted pieces."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector
from mathutils.kdtree import KDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from build_humanoid_runtime import select, triangles
from build_native_humanoid import choose_action, curve_bags
from prepare_native_components import classify
from build_vehicle_runtime import VehicleRig
from native_alignment import uv_world_points, recover_translation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--piece', required=True)
    parser.add_argument('--previous', type=int, required=True)
    parser.add_argument('--version', type=int, required=True)
    parser.add_argument('--tier', choices=('all', 'mobile'), default='all')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    piece = args.piece
    family = piece.split('_')[0]
    folder = ROOT/'assets/generated/meshy'/piece
    out = folder/f'motion/runtime/v{args.version}'
    if out.exists() and any(out.iterdir()):
        raise RuntimeError(f'Output exists: {out}')
    out.mkdir(exist_ok=True, parents=True)
    prior = folder/f'motion/runtime/v{args.previous}/{piece}_animation_source.blend'
    input_version = 3 if family == 'elephant' else 2
    inputs = folder/f'native-input/v{input_version}'
    meta = json.loads((inputs/'input.json').read_text(encoding='utf-8'))
    native = max((folder/'native/rider/idle').glob('v*/model.glb'), key=lambda p: int(p.parent.name[1:]))
    sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (prior, native, inputs/'components.blend')}
    bpy.ops.wm.open_mainfile(filepath=str(prior))
    rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    body = next(o for o in bpy.context.scene.objects if o.type == 'MESH' and o.find_armature() == rig)
    rig.data.pose_position = 'REST'
    ad = rig.animation_data
    old_actions = {t.name: t.strips[0].action.copy() for t in ad.nla_tracks if t.strips}
    rig.animation_data_clear()
    recipe = None if family == 'elephant' else VehicleRig(piece)
    if recipe: recipe.setup()
    # Remove exactly the visible person, then bring back their unchanged source faces.
    bm = bmesh.new(); bm.from_mesh(body.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if classify(piece, body.matrix_world@f.calc_center_median(), recipe) == 'rider'], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(body.data); bm.free(); body.data.update()
    with bpy.data.libraries.load(str(inputs/'components.blend'), link=False) as (available, loaded):
        loaded.objects = ['rider']
    rider = loaded.objects[0]; bpy.context.collection.objects.link(rider)
    rider.data.materials.clear(); rider.data.materials.append(body.data.materials[0])
    for f in rider.data.polygons: f.material_index = 0
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(native))
    added = set(bpy.data.objects)-before
    api = next(o for o in added if o.type == 'ARMATURE')
    skin = next(o for o in added if o.type == 'MESH' and o.find_armature() == api)
    action = choose_action(api)
    api.animation_data.action = action; api.animation_data.action_slot = action.slots[0]
    for track in api.animation_data.nla_tracks: track.mute = True
    api.data.pose_position = 'REST'; bpy.context.view_layer.update()
    translation, alignment = recover_translation(uv_world_points(rider), skin)
    offset = Matrix.Translation(translation)
    api_world = offset@api.matrix_world
    skin_world = offset@skin.matrix_world
    tree = KDTree(len(skin.data.vertices))
    for v in skin.data.vertices: tree.insert(skin_world@v.co, v.index)
    tree.balance()
    prefix = 'Native_'
    select(rig); bpy.ops.object.mode_set(mode='EDIT')
    attachment = 'HorseBack' if family == 'horse' else 'Body'
    for bone in api.data.bones:
        target = rig.data.edit_bones.new(prefix+bone.name)
        # A zero-length EditBone discards its matrix orientation. Establish a
        # direction first, then copy the API rest axes used by its local curves.
        target.head = (0, 0, 0)
        target.tail = (0, 0, .05)
        m = rig.matrix_world.inverted()@api_world@bone.matrix_local
        target.matrix = Matrix.LocRotScale(m.translation, m.to_quaternion(), Vector((1, 1, 1)))
        child = next(iter(bone.children), None)
        target.length = max(.008, ((api_world@child.head_local)-(api_world@bone.head_local)).length) if child else .025
        target.parent = rig.data.edit_bones[prefix+bone.parent.name] if bone.parent else rig.data.edit_bones[attachment]
    if 'Weapon' in rig.data.edit_bones:
        rig.data.edit_bones['Weapon'].parent = rig.data.edit_bones[prefix+'RightHand']
    if family == 'elephant':
        bow = rig.data.edit_bones.new('NativeBow')
        bow.head = rig.data.edit_bones[prefix+'LeftHand'].head
        bow.tail = bow.head+Vector((0, 0, .05))
        bow.parent = rig.data.edit_bones[prefix+'LeftHand']
    bpy.ops.object.mode_set(mode='OBJECT')
    if family == 'elephant':
        bow_group = body.vertex_groups.new(name='NativeBow')
        for face in body.data.polygons:
            if classify(piece, body.matrix_world@face.center) == 'weapon':
                for index in face.vertices:
                    for group in body.vertex_groups: group.remove([index])
                    bow_group.add([index], 1, 'REPLACE')
    if family == 'cannon':
        # A spare ramrod lying beside the bucket is separate from the held tool.
        for vertex in body.data.vertices:
            co = body.matrix_world@vertex.co
            if co.y < -.13 and co.z < .45:
                for group in body.vertex_groups: group.remove([vertex.index])
                body.vertex_groups['Body'].add([vertex.index], 1, 'REPLACE')
    rider.vertex_groups.clear()
    groups = {g.index: rider.vertex_groups.new(name=prefix+g.name) for g in skin.vertex_groups}
    for vertex in rider.data.vertices:
        nearest = tree.find(rider.matrix_world@vertex.co)
        for weight in skin.data.vertices[nearest[1]].groups:
            groups[weight.group].add([vertex.index], weight.weight, 'REPLACE')
    if family == 'cannon':
        # The separated upload has small low accessories near the boots that
        # the native skin sometimes attributes to a hand. They remain planted.
        low = .51 if piece.endswith('red') else .285
        for vertex in rider.data.vertices:
            if (rider.matrix_world@vertex.co).z < low:
                for group in rider.vertex_groups: group.remove([vertex.index])
                rider.vertex_groups[prefix+'Hips'].add([vertex.index],1,'REPLACE')
        if piece.endswith('black'):
            bm=bmesh.new();bm.from_mesh(rider.data)
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
            deform=bm.verts.layers.deform.active
            for _ in range(8):
                changes=[]
                for vertex in bm.verts:
                    co=rider.matrix_world@vertex.co
                    if not (co.x<-.36 and .34<co.z<.55):continue
                    neighbors=[edge.other_vert(vertex) for edge in vertex.link_edges]
                    if not neighbors:continue
                    values={key:value*.5 for key,value in vertex[deform].items()}
                    for neighbor in neighbors:
                        for key,value in neighbor[deform].items():values[key]=values.get(key,0)+value*.5/len(neighbors)
                    values=dict(sorted(values.items(),key=lambda item:item[1],reverse=True)[:4]);total=sum(values.values())
                    changes.append((vertex,{key:value/total for key,value in values.items()}))
                for vertex,values in changes:
                    vertex[deform].clear()
                    for key,value in values.items():vertex[deform][key]=value
            bm.to_mesh(rider.data);bm.free();rider.data.update()
    rider.data.transform(rig.matrix_world.inverted()@rider.matrix_world)
    rider.parent = rig; rider.matrix_parent_inverse = Matrix.Identity(4); rider.matrix_basis = Matrix.Identity(4)
    modifier = rider.modifiers.new('Native rider skin', 'ARMATURE'); modifier.object = rig
    select(body); rider.select_set(True); bpy.ops.object.join()
    # Use changes in the generated performance around its first pose so the
    # original seated/standing pose remains fitted to the saddle and equipment.
    api.data.pose_position = 'POSE'
    start, end = action.frame_range
    bpy.context.scene.frame_set(round(start)); bpy.context.view_layer.update()
    anchor = {pb.name: pb.rotation_quaternion.copy() for pb in api.pose.bones}
    native_samples = []
    for frame in range(math.ceil(start), math.floor(end)+1):
        bpy.context.scene.frame_set(frame); bpy.context.view_layer.update()
        closing = max(0, min(1, (end-frame)/max(1, (end-start)*.15)))
        closing = closing*closing*(3-2*closing)
        values = {}
        for pb in api.pose.bones:
            rotation = pb.rotation_quaternion@anchor[pb.name].inverted()
            if any(part in pb.name for part in ('Leg', 'Foot', 'Toe')):
                rotation = Quaternion()
            if pb.name == 'Hips':
                rotation = Quaternion()
            strength = .38 if family == 'elephant' else .65
            values[prefix+pb.name] = Quaternion().slerp(rotation, strength*closing)
        native_samples.append(values)
    for obj in added: bpy.data.objects.remove(obj, do_unlink=True)
    ad = rig.animation_data_create(); rig.data.pose_position = 'POSE'
    clips = {}
    for name, old in old_actions.items():
        ad.action = old; ad.action_slot = old.slots[0]
        poses = []
        first, last = old.frame_range
        frame_count = len(native_samples) if name == 'idle' else round(last-first)+1
        for index in range(frame_count):
            frame = first+(last-first)*index/max(1, frame_count-1)
            bpy.context.scene.frame_set(math.floor(frame), subframe=frame-math.floor(frame)); bpy.context.view_layer.update()
            poses.append({pb.name: (pb.location.copy(), pb.rotation_quaternion.copy() if pb.rotation_mode == 'QUATERNION' else pb.rotation_euler.to_quaternion(), pb.scale.copy()) for pb in rig.pose.bones if not pb.name.startswith(prefix)})
        result = bpy.data.actions.new(name+'_native_rider'); ad.action = result
        for frame, pose in enumerate(poses):
            sample = native_samples[round(frame/max(1, len(poses)-1)*(len(native_samples)-1))]
            for pb in rig.pose.bones:
                pb.rotation_mode = 'QUATERNION'
                if pb.name.startswith(prefix):
                    pb.location = (0, 0, 0); pb.scale = (1, 1, 1); pb.rotation_quaternion = sample[pb.name]
                else:
                    pb.location, pb.rotation_quaternion, pb.scale = pose[pb.name]
                for prop in ('location', 'rotation_quaternion', 'scale'):
                    pb.keyframe_insert(data_path=prop, frame=frame, group=pb.name)
        ad.action = None
        track = ad.nla_tracks.new(); track.name = name
        strip = track.strips.new(name, 0, result); strip.action_slot = result.slots[0]; strip.extrapolation = 'NOTHING'; track.mute = True
        clips[name] = {'seconds': (len(poses)-1)/30, 'native_rider_motion': str(native.relative_to(ROOT)), 'animal_and_machine_motion': 'existing local articulation'}
    rig.data.pose_position = 'REST'; bpy.context.scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/f'{piece}_animation_source.blend'), compress=True)
    report = {'piece': piece, 'api_rig': 'rider only', 'method': 'Meshy native human rig and generated performance, original geometry and PBR; existing local animal and mechanical articulation', 'native_alignment': alignment, 'clips': clips, 'sources': sources, 'files': {}}
    tiers = [('mobile', 20000, 2048)] if args.tier == 'mobile' else [('desktop', 60000, 4096), ('mobile', 20000, 2048), ('distant', 12000, 1024)]
    for tier, target, resolution in tiers:
        rig.data.pose_position = 'REST'
        if triangles(body) > target:
            select(body); dec = body.modifiers.new('Runtime budget', 'DECIMATE'); dec.ratio = (target-100)/triangles(body)
            bpy.ops.object.modifier_move_up(modifier=dec.name); bpy.ops.object.modifier_apply(modifier=dec.name)
        body.data.validate(clean_customdata=False); body.data.update()
        for image in {n.image for mat in body.data.materials for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image}:
            if max(image.size) > resolution: image.scale(resolution, resolution)
        rig.data.pose_position = 'POSE'; select(body); rig.select_set(True)
        path = out/f'{piece}_{tier}.glb'
        bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True, export_yup=True,
            export_image_format='WEBP', export_image_quality=95, export_animations=True,
            export_animation_mode='NLA_TRACKS', export_frame_range=False, export_force_sampling=True, export_skins=True, export_def_bones=False)
        report['files'][tier] = {'file': path.name, 'triangles': triangles(body), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        print('NATIVE_COMPOSITE', piece, tier, report['files'][tier], flush=True)
    report['sources_unchanged'] = all(hashlib.sha256((ROOT/k).read_bytes()).hexdigest() == v for k, v in sources.items()); assert report['sources_unchanged']
    (out/'runtime.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__': main()
