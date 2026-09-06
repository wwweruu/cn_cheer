"""Assemble Meshy-generated clips with original PBR, rigid equipment and grounded feet."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector, Quaternion
from mathutils.kdtree import KDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from build_humanoid_runtime import select, triangles
from repair_humanoid_runtime import TOPS, split_at, weapon
from native_alignment import uv_world_points, recover_translation


def reviewed_pedestal(folder, piece, material):
    version = {'soldier_red': 6, 'soldier_black': 11, 'general_black': 4,
               'advisor_red': 4, 'general_red': 2, 'advisor_black': 2}[piece]
    path = folder/f'motion/runtime/v{version}/{piece}_animation_source.blend'
    with bpy.data.libraries.load(str(path), link=False) as (available, loaded):
        loaded.objects = available.objects
    for obj in loaded.objects:
        bpy.context.collection.objects.link(obj)
    mesh = next(obj for obj in loaded.objects if obj.type == 'MESH' and obj.vertex_groups.get('FixedPedestal'))
    bpy.context.view_layer.update()
    mesh.data.transform(mesh.matrix_world); mesh.parent = None; mesh.matrix_world = Matrix.Identity(4); mesh.modifiers.clear()
    fixed = mesh.vertex_groups['FixedPedestal'].index
    bm = bmesh.new(); bm.from_mesh(mesh.data); weights = bm.verts.layers.deform.active
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v[weights].get(fixed, 0) < .999], context='VERTS')
    bm.to_mesh(mesh.data); bm.free(); mesh.data.update()
    mesh.data.materials.clear(); mesh.data.materials.append(material)
    for polygon in mesh.data.polygons: polygon.material_index = 0
    for obj in loaded.objects:
        if obj != mesh: bpy.data.objects.remove(obj, do_unlink=True)
    return mesh, path


def equipment(piece, co):
    x, y, z = co
    if piece == 'soldier_red':
        if x < -.34 and z < .915:
            return 'RightHand'
        # The shield is an oblique plate; the forearm remains behind it.
        if .15 < x < .455 and .622 < z < 1.145 and y < .035 + 1.10*(x-.15):
            return 'LeftHand'
        return None
    return weapon(piece, co)


def choose_action(rig):
    ad = rig.animation_data
    actions = ([ad.action] if ad.action else []) + [t.strips[0].action for t in ad.nla_tracks if t.strips]
    return max(actions, key=lambda a: a.frame_range[1]-a.frame_range[0])


def curve_bags(action):
    for layer in action.layers:
        for strip in layer.strips:
            for slot in action.slots:
                bag = strip.channelbag(slot, ensure=False)
                if bag:
                    yield bag


def evaluated_points(body, indices):
    obj = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = obj.to_mesh()
    values = np.empty(len(mesh.vertices)*3, dtype=np.float32)
    mesh.vertices.foreach_get('co', values)
    coords = values.reshape(-1, 3)[indices]
    world = np.asarray(obj.matrix_world)
    result = coords@world[:3, :3].T+world[:3, 3]
    obj.to_mesh_clear()
    return result


def retarget_action(source_rig, source_action, target_rig, name):
    """Preserve model-space motion across exporter-specific bone roll axes."""
    source_ad = source_rig.animation_data_create()
    source_ad.action = source_action
    source_ad.action_slot = source_action.slots[0]
    for track in source_ad.nla_tracks:
        track.mute = True
    source_rig.data.pose_position = 'POSE'
    samples = []
    for frame in range(math.ceil(source_action.frame_range[0]), math.floor(source_action.frame_range[1])+1):
        bpy.context.scene.frame_set(frame); bpy.context.view_layer.update()
        desired = {b.name: source_rig.pose.bones[b.name].matrix@source_rig.data.bones[b.name].matrix_local.inverted()@b.matrix_local
                   for b in target_rig.data.bones if b.name in source_rig.pose.bones}
        pose = []
        for bone in target_rig.data.bones:
            if bone.name not in desired:
                continue
            kwargs = {'parent_matrix': desired[bone.parent.name], 'parent_matrix_local': bone.parent.matrix_local} if bone.parent and bone.parent.name in desired else {}
            basis = bone.convert_local_to_pose(desired[bone.name], bone.matrix_local, invert=True, **kwargs)
            loc, rot, scale = basis.decompose()
            pose.append((bone.name, loc, rot, scale))
        samples.append(pose)
    result = bpy.data.actions.new(name+'_source')
    target_ad = target_rig.animation_data_create(); target_ad.action = result
    for frame, pose in enumerate(samples):
        for bone, loc, rot, scale in pose:
            pb = target_rig.pose.bones[bone]; pb.rotation_mode = 'QUATERNION'
            pb.location, pb.rotation_quaternion, pb.scale = loc, rot, scale
            for prop in ('location', 'rotation_quaternion', 'scale'):
                pb.keyframe_insert(data_path=prop, frame=frame, group=bone)
    target_ad.action = None
    result.use_fake_user = True
    target_rig.data.pose_position = 'REST'
    return result


def stride_window(rig, start, end):
    """Find a repeated leg phase in the generated clip, excluding still poses."""
    names = [name for name in ('Hips','LeftUpLeg','RightUpLeg','LeftLeg','RightLeg','LeftFoot','RightFoot') if name in rig.pose.bones]
    frames = list(range(math.ceil(start), math.floor(end)+1))
    rotations = []
    for frame in frames:
        bpy.context.scene.frame_set(frame); bpy.context.view_layer.update()
        rotations.append([rig.pose.bones[name].rotation_quaternion.copy() for name in names])
    best = None
    for i in range(8, max(9,len(frames)-33)):
        for period in range(28, min(51,len(frames)-i-3)):
            j = i+period
            motion = sum(1-abs(a.dot(b)) for a,b in zip(rotations[i][1:3],rotations[i+period//2][1:3]))
            if motion < .005:
                continue
            mismatch = sum(1-abs(a.dot(b)) for a,b in zip(rotations[i],rotations[j]))
            neighbor = sum(1-abs(a.dot(b)) for a,b in zip(rotations[i+1],rotations[j+1]))
            score = mismatch+.4*neighbor+.0004*((period-38)/12)**2
            if best is None or score < best[0]: best = (score,frames[i],frames[j])
    return (best[1],best[2]) if best else (math.ceil(start+(end-start)*.22),math.ceil(start+(end-start)*.22)+38)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--piece', required=True)
    p.add_argument('--version', type=int, required=True)
    p.add_argument('--tier', choices=('all', 'mobile'), default='all')
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    piece = a.piece
    folder = ROOT/'assets/generated/meshy'/piece
    out = folder/f'motion/runtime/v{a.version}'
    if out.exists() and any(out.iterdir()):
        raise RuntimeError(f'Output already exists: {out}')
    out.mkdir(parents=True, exist_ok=True)
    source = folder/f'runtime/v1/{piece}_desktop.glb'
    input_version = 2 if piece == 'soldier_red' else 1
    cut = json.loads((folder/f'rig-input/v{input_version}/input.json').read_text(encoding='utf-8'))['base_cut']
    top = TOPS[piece]-.0012
    if piece == 'soldier_black':
        # The upload proxy cut at .205 removes most of the visible shoes.
        # Runtime geometry uses the source plate height, not the upload crop.
        cut = TOPS[piece]+.006
    sources = {str(source.relative_to(ROOT)): hashlib.sha256(source.read_bytes()).hexdigest()}
    ledger = json.loads((ROOT/'.meshy/live/ledger.json').read_text(encoding='utf-8'))['jobs']
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 30
    bpy.ops.import_scene.gltf(filepath=str(source))
    base = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
    base.data.transform(base.matrix_world)
    base.parent = None
    base.matrix_world = Matrix.Identity(4)
    base.data.update()
    original_points = uv_world_points(base)
    original_body = base.copy(); original_body.data = base.data.copy()
    bpy.context.collection.objects.link(original_body)
    material = base.data.materials[0]
    layer = base.data.uv_layers.active
    face = max((f for f in base.data.polygons if f.normal.z > .9 and abs(f.center.z-TOPS[piece]) < .01), key=lambda f: f.area)
    cap_uv = sum((layer.data[i].uv for i in face.loop_indices), Vector((0, 0)))/len(face.loop_indices)
    split_at(original_body, cut, True, cap_uv)
    bpy.data.objects.remove(base, do_unlink=True)
    base, base_source = reviewed_pedestal(folder, piece, material)
    sources[str(base_source.relative_to(ROOT))] = hashlib.sha256(base_source.read_bytes()).hexdigest()
    clips = {}
    rig = body = None
    clip_sources = {}
    for name in ('idle', 'walk', 'run', 'attack', 'hit', 'death'):
        candidates = list((folder/f'native/body/{name}').glob('v*/model.glb'))
        native = max(candidates, key=lambda p: int(p.parent.name[1:])) if candidates else folder/f'native/body/{name}/v1/model.glb'
        old_version = 2 if piece == 'soldier_red' and name == 'death' else 1
        path = native if native.exists() else folder/f'motion/{name}/v{old_version}/model.glb'
        if name in ('walk', 'run') and not native.exists():
            rig_clip = f'{"walking" if name == "walk" else "running"}.glb'
            native_rigs = list((folder/'native/body/rig').glob(f'v*/{rig_clip}'))
            path = max(native_rigs, key=lambda p: int(p.parent.name[1:])) if native_rigs else folder/f'motion/rig/v1/{rig_clip}'
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(path))
        added = set(bpy.data.objects)-before
        imported_rig = next(o for o in added if o.type == 'ARMATURE')
        action = choose_action(imported_rig).copy()
        action.name = name+'_native_source'
        action.use_fake_user = True
        job_key = str(path.parent.relative_to(ROOT/'assets/generated/meshy')).replace('\\', '/')
        clip_sources[name] = {'path': str(path.relative_to(ROOT)), 'text_to_motion': 'motion_task_id' in ledger.get(job_key, {}).get('params', {})}
        sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        if rig is None:
            rig = imported_rig
            body = next(o for o in added if o.type == 'MESH' and o.find_armature() == rig)
            rig.animation_data_clear()
            rig.data.pose_position = 'REST'
            bpy.context.view_layer.update()
            translation, alignment = recover_translation(original_points, body)
            rig.location += translation
            bpy.context.view_layer.update()
            for obj in added-{rig, body}:
                bpy.data.objects.remove(obj, do_unlink=True)
            clips[name] = retarget_action(rig, action, rig, name)
        else:
            clips[name] = retarget_action(imported_rig, action, rig, name)
            for obj in added:
                bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()
    # The returned skin can exclude equipment. Transfer the native weights to
    # the complete original surface, with exact UV correspondence when present.
    tree = KDTree(len(body.data.vertices))
    for vertex in body.data.vertices:
        tree.insert(body.matrix_world@vertex.co, vertex.index)
    tree.balance()
    api_uv = {}
    layer = body.data.uv_layers.active
    for loop in body.data.loops:
        api_uv[tuple(round(value, 5) for value in layer.data[loop.index].uv)] = loop.vertex_index
    source_uv = {}
    layer = original_body.data.uv_layers.active
    for loop in original_body.data.loops:
        source_uv[loop.vertex_index] = tuple(round(value, 5) for value in layer.data[loop.index].uv)
    groups = {group.index: original_body.vertex_groups.new(name=group.name) for group in body.vertex_groups}
    for vertex in original_body.data.vertices:
        world = original_body.matrix_world@vertex.co
        index = api_uv.get(source_uv[vertex.index])
        if index is None or ((body.matrix_world@body.data.vertices[index].co)-world).length > .002:
            index = tree.find(world)[1]
        for weight in body.data.vertices[index].groups:
            groups[weight.group].add([vertex.index], weight.weight, 'REPLACE')
    bpy.data.objects.remove(body, do_unlink=True)
    body = original_body
    body.data.transform(body.matrix_world)
    body.parent = None
    body.matrix_world = Matrix.Identity(4)
    body.modifiers.clear()
    body.data.materials.clear(); body.data.materials.append(material)
    for f in body.data.polygons:
        f.material_index = 0
    # Keep contact bridges continuous while assigning equipment to the hand.
    bm = bmesh.new(); bm.from_mesh(body.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.000001)
    tags = bm.faces.layers.int.new('native_equipment')
    hands = ['', 'RightHand', 'LeftHand']
    shader = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = shader.inputs['Base Color'].links[0].from_node.image
    pixels = np.empty(len(tex.pixels), dtype=np.float32); tex.pixels.foreach_get(pixels)
    pixels = pixels.reshape(tex.size[1], tex.size[0], 4)
    uv_layer = bm.loops.layers.uv.active
    for f in bm.faces:
        tag = equipment(piece, f.calc_center_median())
        if piece == 'soldier_red' and tag == 'LeftHand' and f.calc_center_median().z > 1.015:
            uv = sum((loop[uv_layer].uv for loop in f.loops), Vector((0, 0)))/len(f.loops)
            red, green, blue = pixels[int(uv.y*tex.size[1])%tex.size[1], int(uv.x*tex.size[0])%tex.size[0], :3]
            if red > .46 and green > .39 and red < green*1.30:
                tag = None
        f[tags] = hands.index(tag) if tag else 0
    bm.to_mesh(body.data); bm.free(); body.data.update()
    tagged = {}
    attribute = body.data.attributes['native_equipment']
    for face in body.data.polygons:
        tag = attribute.data[face.index].value
        if tag:
            for index in face.vertices:
                tagged[index] = hands[tag]
    for index, name in tagged.items():
        for group in body.vertex_groups:
            group.remove([index])
        body.vertex_groups[name].add([index], 1, 'REPLACE')
    ankle_anchors = {}
    if piece.startswith('soldier') or piece == 'general_black':
        boot_top = {'soldier_red': .315, 'soldier_black': .28, 'general_black': .33}[piece]
        for side, sign in [('Left', 1), ('Right', -1)]:
            band = [v.co.copy() for v in body.data.vertices if v.index not in tagged
                    and abs(v.co.z-boot_top) < .02 and v.co.x*sign > .035 and abs(v.co.x) < .26]
            ankle_anchors[side+'Foot'] = sum(band, Vector((0,0,0)))/len(band)
        # Native black-infantry skin assigns most of the calf to UpLeg and
        # almost none to Leg. A foot correction cannot repair that discontinuity.
        # Rebuild the calf/ankle chain, including a continuous boot-cuff blend.
        def smoothstep(lo, hi, value):
            t = max(0, min(1, (value-lo)/(hi-lo)))
            return t*t*(3-2*t)
        for vertex in body.data.vertices:
            if vertex.index in tagged:
                continue
            center_x = (rig.matrix_world@rig.data.bones['Hips'].head_local).x
            side = 'Left' if vertex.co.x > center_x else 'Right'
            knee = (rig.matrix_world@rig.data.bones[side+'Leg'].head_local).z
            if vertex.co.z > knee+.07:
                continue
            shin = smoothstep(boot_top-.025, boot_top+.035, vertex.co.z)
            thigh = smoothstep(knee-.035, knee+.065, vertex.co.z)
            weights = {side+'Foot':1-shin, side+'Leg':shin*(1-thigh), side+'UpLeg':shin*thigh}
            # The scanned coat bridges the inner legs. Keep its centre on the
            # pelvis instead of splitting neighboring cloth vertices by side.
            cloth = (1-smoothstep(.025,.080,abs(vertex.co.x-center_x)))*smoothstep(boot_top+.05,boot_top+.14,vertex.co.z)
            weights = {key:value*(1-cloth) for key,value in weights.items()}
            weights['Hips'] = cloth
            for group in body.vertex_groups:
                group.remove([vertex.index])
            for group_name, weight in weights.items():
                if weight > 1e-7:
                    body.vertex_groups[group_name].add([vertex.index], weight, 'REPLACE')
    # Robes follow the pelvis and spine; boots keep their own foot joints.
    if piece == 'general_black':
        # Long rear/side cape surfaces are far from the clean upload's human
        # skin. Nearest-joint transfer incorrectly attached them to the knees.
        rough_node = shader.inputs['Roughness'].links[0].from_node
        rough_image = rough_node.inputs[0].links[0].from_node.image
        rough_pixels = np.empty(len(rough_image.pixels), dtype=np.float32)
        rough_image.pixels.foreach_get(rough_pixels)
        rough_pixels = rough_pixels.reshape(rough_image.size[1],rough_image.size[0],4)
        roughness = {}
        layer = body.data.uv_layers.active
        for loop in body.data.loops:
            uv = layer.data[loop.index].uv
            roughness.setdefault(loop.vertex_index,[]).append(float(rough_pixels[int(uv.y*rough_image.size[1])%rough_image.size[1],int(uv.x*rough_image.size[0])%rough_image.size[0],1]))
        for v in body.data.vertices:
            x,y,z = v.co
            fabric = smoothstep(.76,.93,float(np.median(roughness.get(v.index,[0]))))
            cape = fabric*smoothstep(-.03,.035,y)*max(smoothstep(.13,.19,abs(x)),smoothstep(.06,.12,y))*smoothstep(.20,.26,z)
            if z > .196:
                # Texture seams contain occasional low-roughness texels. The
                # rear curtain remains one surface despite those pixel outliers.
                cape = max(cape,smoothstep(.10,.145,y),smoothstep(.21,.28,abs(x))*smoothstep(-.06,.02,y))
                if z < .68:
                    distances=[]
                    shoe_distances=[]
                    for side in ('Left','Right'):
                        foot=rig.matrix_world@rig.data.bones[side+'Foot'].head_local
                        knee=rig.matrix_world@rig.data.bones[side+'Leg'].head_local
                        toe=rig.matrix_world@rig.data.bones[side+'ToeBase'].head_local
                        if z >= foot.z+.025:
                            centre=foot.lerp(knee,max(0,min(1,(z-foot.z)/(knee.z-foot.z))))
                        else:
                            span=Vector((toe.x-foot.x,toe.y-foot.y,0))
                            offset=Vector((x-foot.x,y-foot.y,0))
                            centre=foot.lerp(toe,max(0,min(1,offset.dot(span)/span.length_squared)))
                            shoe_distances.append(math.hypot(x-centre.x,y-centre.y))
                        distances.append(math.hypot(x-centre.x,y-centre.y))
                    cape=max(cape,smoothstep(.115,.155,min(distances)))
                    if shoe_distances and min(shoe_distances)<.105:
                        cape=0
            if v.index in tagged or cape < 1e-6:
                continue
            upper = smoothstep(.91,1.24,z)
            weights = {group.group:group.weight*(1-cape) for group in v.groups}
            for name,amount in [('Hips',1-upper),('Spine02',upper)]:
                index=body.vertex_groups[name].index
                weights[index]=weights.get(index,0)+amount*cape
            for group in body.vertex_groups:
                group.remove([v.index])
            for index,value in weights.items():
                if value > 1e-7:body.vertex_groups[index].add([v.index],value,'REPLACE')
    if piece.startswith('advisor'):
        for v in body.data.vertices:
            x, y, z = v.co
            if z < .88:
                foot = z < top+.115 and abs(x) < .15 and y < -.025
                name = ('LeftFoot' if x > 0 else 'RightFoot') if foot else 'Hips'
                for group in body.vertex_groups:
                    group.remove([v.index])
                body.vertex_groups[name].add([v.index], 1, 'REPLACE')
    body.data.transform(rig.matrix_world.inverted())
    body.parent = rig
    body.matrix_parent_inverse = Matrix.Identity(4)
    body.matrix_basis = Matrix.Identity(4)
    modifier = body.modifiers.new('Meshy native skin', 'ARMATURE'); modifier.object = rig
    select(rig); bpy.ops.object.mode_set(mode='EDIT')
    fixed = rig.data.edit_bones.new('FixedPedestal')
    fixed.head = rig.matrix_world.inverted()@Vector((0, 0, 0))
    fixed.tail = fixed.head+Vector((0, 0, 5))
    bpy.ops.object.mode_set(mode='OBJECT')
    base.vertex_groups.clear(); base.vertex_groups.new(name='FixedPedestal').add(list(range(len(base.data.vertices))), 1, 'REPLACE')
    # Apply the same rig-local transform to the fixed base before joining.
    base.data.transform(rig.matrix_world.inverted())
    base.parent = rig; base.matrix_parent_inverse = Matrix.Identity(4); base.matrix_basis = Matrix.Identity(4)
    select(body); base.select_set(True); bpy.ops.object.join()
    body.name = piece+'_animated'; rig.name = piece+'_native_rig'
    feet_groups = {g.index for g in body.vertex_groups if 'Foot' in g.name or 'Toe' in g.name}
    contact_height = {'soldier_red': .315, 'soldier_black': .28, 'general_black': .33}.get(piece, top+.13)
    foot_indices = np.array([v.index for v in body.data.vertices if v.index not in tagged
        and (rig.matrix_world@v.co).z < contact_height
        and sum(g.weight for g in v.groups if g.group in feet_groups) > .45], dtype=np.int32)
    ad = rig.animation_data_create(); rig.data.pose_position = 'POSE'
    hips = rig.pose.bones['Hips']
    rest_hip = rig.matrix_world@hips.bone.head_local
    translation_basis = (rig.matrix_world@hips.bone.matrix_local).to_3x3().inverted()
    report = {'piece': piece, 'api_rig': True, 'method': 'Meshy generated and preset clips, rigid equipment, original PBR and fixed pedestal',
              'sources': sources, 'clip_sources': clip_sources, 'native_alignment': alignment, 'rigid_vertices': len(tagged), 'foot_vertices': len(foot_indices), 'clips': {}, 'files': {}}
    for name, source_action in clips.items():
        ad.action = source_action; ad.action_slot = source_action.slots[0]
        start, end = source_action.frame_range
        bpy.context.scene.frame_set(round(start)); bpy.context.view_layer.update()
        idle_anchor = {pb.name: pb.rotation_quaternion.copy() for pb in rig.pose.bones}
        # A board step uses one stride, not all three strides of a four-second generation.
        if name in ('walk', 'run') and end-start > 55:
            start, end = stride_window(rig, start, end)
        samples = []
        corrections = []
        for frame in range(math.ceil(start), math.floor(end)+1):
            bpy.context.scene.frame_set(frame); bpy.context.view_layer.update()
            if name == 'idle':
                for pb in rig.pose.bones:
                    pb.rotation_quaternion = pb.rotation_quaternion@idle_anchor[pb.name].inverted()
                    pb.location = (0, 0, 0)
                    pb.scale = (1, 1, 1)
                    if pb.name == 'Hips' or any(part in pb.name for part in ('Leg', 'Foot', 'Toe')):
                        pb.rotation_quaternion = Quaternion()
                bpy.context.view_layer.update()
            if (piece.startswith('soldier') or piece == 'general_black') and name in ('walk', 'run'):
                motion_strength = .55 if piece == 'general_black' else .66
                for pb in rig.pose.bones:
                    pb.rotation_quaternion = Quaternion().slerp(pb.rotation_quaternion, motion_strength)
                bpy.context.view_layer.update()
            if name in ('walk', 'run'):
                # Keep carried equipment in the authored grip orientation;
                # retain generated upper-body changes around the first pose.
                for pb in rig.pose.bones:
                    if pb.name not in ('Hips', 'FixedPedestal') and not any(part in pb.name for part in ('Leg', 'Foot', 'Toe')):
                        raw = pb.rotation_quaternion
                        # Soldier motion was reduced above, so reduce its
                        # anchor by the same amount before taking the delta.
                        anchor = Quaternion().slerp(idle_anchor[pb.name], motion_strength) if piece.startswith('soldier') or piece == 'general_black' else idle_anchor[pb.name]
                        pb.rotation_quaternion = Quaternion().slerp(raw@anchor.inverted(), .5)
                bpy.context.view_layer.update()
            if name in ('idle', 'walk', 'run', 'hit') and (piece.startswith('soldier') or piece == 'general_black'):
                # Rigid soles cannot twist with the toe and ankle skin blend.
                for foot_name in ('LeftFoot', 'RightFoot'):
                    pb = rig.pose.bones[foot_name]
                    pose = pb.matrix.copy()
                    rest_rotation = pb.bone.matrix_local.to_quaternion()
                    pose_rotation = pose.to_quaternion()
                    corrected = rest_rotation.slerp(pose_rotation, .18)
                    corrected_pose = Matrix.LocRotScale(pose.translation, corrected, pose.to_scale())
                    anchor = rig.matrix_world.inverted()@ankle_anchors[foot_name]
                    shin_point = pb.parent.matrix@pb.parent.bone.matrix_local.inverted()@anchor
                    foot_point = corrected_pose@pb.bone.matrix_local.inverted()@anchor
                    corrected_pose.translation += shin_point-foot_point
                    pb.matrix = corrected_pose
                bpy.context.view_layer.update()
            current = rig.matrix_world@hips.head
            hips.location += translation_basis@Vector((rest_hip.x-current.x, rest_hip.y-current.y, 0))
            bpy.context.view_layer.update()
            if len(foot_indices) and name != 'death':
                lowest = float(evaluated_points(body, foot_indices)[:, 2].min())
                correction = top+.001-lowest
                hips.location += translation_basis@Vector((0, 0, correction))
                corrections.append(correction)
            bpy.context.view_layer.update()
            samples.append([(b.name, b.location.copy(), b.rotation_quaternion.copy(), b.scale.copy()) for b in rig.pose.bones])
        action = bpy.data.actions.new(name)
        ad.action = action
        if name in ('idle', 'walk', 'run'):
            close_frames = min(24 if name == 'idle' else 6, len(samples)-1)
            for index in range(len(samples)-close_frames, len(samples)):
                t = (index-(len(samples)-close_frames))/max(1,close_frames-1)
                t = t*t*(3-2*t)
                samples[index] = [(bone,loc.lerp(anchor[1],t),rot.slerp(anchor[2],t),scale.lerp(anchor[3],t))
                                  for (bone,loc,rot,scale),anchor in zip(samples[index],samples[0])]
            samples[-1] = samples[0]
        for frame, pose in enumerate(samples):
            for bone, loc, rot, scale in pose:
                pb = rig.pose.bones[bone]; pb.rotation_mode = 'QUATERNION'
                pb.location, pb.rotation_quaternion, pb.scale = loc, rot, scale
            bpy.context.view_layer.update()
            if name in ('idle', 'walk', 'run') and len(foot_indices):
                lowest = float(evaluated_points(body, foot_indices)[:, 2].min())
                hips.location += translation_basis@Vector((0,0,top+.001-lowest))
                bpy.context.view_layer.update()
            for pb in rig.pose.bones:
                for prop in ('location', 'rotation_quaternion', 'scale'):
                    pb.keyframe_insert(data_path=prop, frame=frame, group=pb.name)
        for bag in curve_bags(action):
            for curve in bag.fcurves:
                for key in curve.keyframe_points:
                    key.interpolation = 'LINEAR'
        ad.action = None
        track = ad.nla_tracks.new(); track.name = name
        strip = track.strips.new(name, 0, action); strip.action_slot = action.slots[0]
        strip.extrapolation = 'NOTHING'; track.mute = True
        report['clips'][name] = {'frames': [0, len(samples)-1], 'seconds': (len(samples)-1)/30,
                                 'source_frames': [start,end], 'loop_closed': name in ('idle','walk','run'),
                                 'ground_correction': [min(corrections), max(corrections)] if corrections else [0, 0]}
    rig.data.pose_position = 'REST'; bpy.context.scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/f'{piece}_animation_source.blend'), compress=True)
    tiers = [('mobile', 20000, 2048)] if a.tier == 'mobile' else [('desktop', 60000, 4096), ('mobile', 20000, 2048), ('distant', 12000, 1024)]
    for tier, target, resolution in tiers:
        rig.data.pose_position = 'REST'
        if triangles(body) > target:
            select(body); dec = body.modifiers.new('Runtime budget', 'DECIMATE'); dec.ratio = (target-100)/triangles(body)
            bpy.ops.object.modifier_move_up(modifier=dec.name); bpy.ops.object.modifier_apply(modifier=dec.name)
        body.data.validate(clean_customdata=False); body.data.update()
        for image in {n.image for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image}:
            if max(image.size) > resolution:
                image.scale(resolution, resolution)
        rig.data.pose_position = 'POSE'; select(body); rig.select_set(True)
        path = out/f'{piece}_{tier}.glb'
        bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True, export_yup=True,
                                  export_image_format='WEBP', export_image_quality=95, export_animations=True,
                                  export_animation_mode='NLA_TRACKS', export_frame_range=False,
                                  export_force_sampling=True, export_skins=True, export_def_bones=False)
        report['files'][tier] = {'file': path.name, 'triangles': triangles(body), 'bytes': path.stat().st_size,
                                 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        print('NATIVE_RUNTIME', piece, tier, report['files'][tier], flush=True)
    report['sources_unchanged'] = all(hashlib.sha256((ROOT/k).read_bytes()).hexdigest() == v for k, v in sources.items())
    assert report['sources_unchanged']
    (out/'runtime.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
