"""Contact-constrained riders and explicitly authored elephant foot trajectories.

API rider motions are retained as the upper-body performance layer. Elephant
gait is local authoring, never labelled an API-generated quadruped result.
"""
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
sys.path.insert(0, str(Path(__file__).parent))
from build_humanoid_runtime import select, triangles
from build_native_humanoid import curve_bags
from contact_kinematics import solve_chain, smooth, floor_cycle
from prepare_native_components import classify
from repair_humanoid_runtime import split_at


def weight(mesh, indices, values):
    for group in mesh.vertex_groups:
        group.remove(indices)
    for name, value in values.items():
        if value > 1e-7:
            group = mesh.vertex_groups.get(name) or mesh.vertex_groups.new(name=name)
            group.add(indices, value, 'REPLACE')


def elephant_rig(piece, rig, body):
    red = piece.endswith('red')
    top = .156 if red else .112
    # Remove the scanned foot/plate bridges and close both newly exposed faces.
    source = ROOT/'assets/generated/meshy'/piece/f'runtime/v1/{piece}_desktop.glb'
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(source))
    added = set(bpy.data.objects)-before
    base = next(o for o in added if o.type == 'MESH')
    base.data.transform(base.matrix_world); base.parent = None; base.matrix_world = Matrix.Identity(4)
    base.data.update()
    layer = base.data.uv_layers.active
    face = max((f for f in base.data.polygons if f.normal.z > .9 and abs(f.center.z-top) < .009), key=lambda f:f.area)
    uv = sum((layer.data[i].uv for i in face.loop_indices), Vector((0,0)))/len(face.loop_indices)
    material = body.data.materials[0]
    base.data.materials.clear(); base.data.materials.append(material)
    for f in base.data.polygons: f.material_index = 0
    split_at(base, top-.0015, False, uv)
    edge = [v.co for v in base.data.vertices if v.co.z > top-.006]
    cx, cy = [(max(v[i] for v in edge)+min(v[i] for v in edge))*.5 for i in (0,1)]
    rx, ry = [(max(v[i] for v in edge)-min(v[i] for v in edge))*.492 for i in (0,1)]
    bm = bmesh.new(); bm.from_mesh(base.data); layer = bm.loops.layers.uv.active
    center = bm.verts.new((cx, cy, top-.0012))
    rim = [bm.verts.new((cx+rx*math.cos(i*math.tau/128), cy+ry*math.sin(i*math.tau/128), top-.0012)) for i in range(128)]
    for i in range(128):
        f = bm.faces.new((center, rim[i], rim[(i+1)%128]))
        for loop in f.loops: loop[layer].uv = uv+Vector((loop.vert.co.x*.01, loop.vert.co.y*.01))
    bm.to_mesh(base.data); bm.free(); base.data.update()
    body.data.transform(body.matrix_world); body.parent = None; body.matrix_world = Matrix.Identity(4)
    body.modifiers.clear()
    cut = top+.012
    split_at(body, cut, True, uv)
    for v in body.data.vertices:
        v.co.z -= (cut-top)*(1-smooth(cut, cut+.035, v.co.z))
    body.data.update()
    # Four isolated lower legs, separated from the forward trunk and tusks.
    leg_top = .39 if red else .32
    trunk_boundary = -.285 if red else -.20
    points = [v.co.copy() for v in body.data.vertices if top+.025 < v.co.z < top+.10 and v.co.y > trunk_boundary]
    middle = .065 if red else .165
    definitions = {}
    feet = {}
    for end in ('F', 'R'):
        for side, sign in [('L',-1),('R',1)]:
            pts = [v for v in points if v.x*sign > .025 and ((v.y < middle) == (end == 'F'))]
            assert len(pts) > 20, (piece,end,side,len(pts))
            xyz = np.median(np.array([list(v) for v in pts]),axis=0)
            prefix = 'Elephant'+end+side
            foot = Vector((float(xyz[0]),float(xyz[1]),top+.035))
            hip = Vector((foot.x,foot.y, .49 if red else .41))
            knee = hip.lerp(foot,.53); knee.y += (-.012 if end == 'F' else .022)
            definitions[prefix+'Upper'] = (hip,'Body')
            definitions[prefix+'Lower'] = (knee,prefix+'Upper')
            definitions[prefix+'Foot'] = (foot,prefix+'Lower')
            feet[prefix] = {'foot':foot,'hip':hip,'knee':knee,'end':end,'side':side}
    definitions['ElephantHead'] = (Vector((0,-.20 if red else -.10,.61 if red else .51)),'Body')
    definitions['ElephantTrunk'] = (Vector((0,-.34 if red else -.28,.40 if red else .34)),'ElephantHead')
    tail_y = max(d['foot'].y for d in feet.values())+.072
    definitions['ElephantTail'] = (Vector((0,tail_y,.57 if red else .48)),'Body')
    select(rig); bpy.ops.object.mode_set(mode='EDIT')
    for name,(head,parent) in definitions.items():
        b = rig.data.edit_bones.new(name); b.head = head; b.tail = head+Vector((0,.05,0)); b.parent = rig.data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for name in definitions:
        if not body.vertex_groups.get(name): body.vertex_groups.new(name=name)
    for v in body.data.vertices:
        old = {body.vertex_groups[g.group].name:g.weight for g in v.groups}
        if any(n.startswith('Native_') or n == 'NativeBow' for n in old):
            continue
        x,y,z = v.co
        values = {'Body':1}
        if y > tail_y and abs(x) < .052 and z < (.62 if red else .52):
            tail = 1-smooth(.48 if red else .40,.60 if red else .51,z)
            values = {'Body':1-tail,'ElephantTail':tail}
        elif z < leg_top+.065 and y > trunk_boundary:
            body_blend = smooth(leg_top-.025,leg_top+.065,z)
            sole = 1-smooth(top+.035,top+.090,z)
            distances = {prefix:math.hypot(x-d['foot'].x,y-d['foot'].y) for prefix,d in feet.items()}
            nearest = min(distances,key=distances.get)
            separation = smooth(top+.075,top+.135,z)
            influences = {prefix:(1-separation if prefix==nearest else 0)+separation*(1-smooth(.060 if red else .058,.105 if red else .095,distance)) for prefix,distance in distances.items()}
            total = max(1,sum(influences.values()))
            influences = {prefix:amount/total*(1-body_blend) for prefix,amount in influences.items()}
            values = {'Body':1-sum(influences.values())}
            for prefix,amount in influences.items():
                lower_blend = 1-smooth(feet[prefix]['knee'].z-.03,feet[prefix]['knee'].z+.03,z)
                values[prefix+'Upper'] = amount*(1-lower_blend)
                values[prefix+'Lower'] = amount*lower_blend*(1-sole)
                values[prefix+'Foot'] = amount*lower_blend*sole
        elif y < (-.20 if red else -.10) and z < (.77 if red else .63):
            head = 1-smooth(-.29 if red else -.19,-.18 if red else -.07,y)
            trunk = (1-smooth(.34 if red else .28,.50 if red else .43,z))*(1-smooth(-.35 if red else -.31,-.27 if red else -.23,y))
            values = {'Body':1-head,'ElephantHead':head*(1-trunk),'ElephantTrunk':head*trunk}
        weight(body,[v.index],values)
    base.vertex_groups.clear(); base.vertex_groups.new(name='FixedPedestal').add(list(range(len(base.data.vertices))),1,'REPLACE')
    select(body); base.select_set(True); bpy.ops.object.join()
    body.data.transform(rig.matrix_world.inverted()); body.parent = rig; body.matrix_parent_inverse = Matrix.Identity(4); body.matrix_basis = Matrix.Identity(4)
    mod = body.modifiers.new('Contact-controlled elephant and native rider','ARMATURE'); mod.object = rig
    return feet, top


def constrain_horse_hands(rig, piece):
    back = rig.pose.bones['HorseBack']; space = back.matrix@back.bone.matrix_local.inverted()
    errors = []
    for side in ('Right','Left'):
        tip = rig.pose.bones['Native_'+side+'Hand']
        if side == 'Right':
            rest_target = tip.bone.head_local.copy()
            rest_target.z += .014
            rotation = (space@tip.bone.matrix_local).to_quaternion()
        else:
            rest_target = Vector((.063,-.09,.717) if piece.endswith('red') else (.054,-.10,.625))
            rotation = (space@Matrix.Rotation(math.radians(-55),4,'Z')@tip.bone.matrix_local).to_quaternion()
        target = space@rest_target
        pole = space@Vector((.16 if side=='Left' else -.18,.055,.74 if piece.endswith('red') else .64))
        errors.append(solve_chain(rig,'Native_'+side+'Arm','Native_'+side+'ForeArm',tip.name,target,pole,rotation))
    return max(errors)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--piece',required=True); p.add_argument('--previous',type=int,required=True); p.add_argument('--version',type=int,required=True)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    piece = args.piece; family = piece.split('_')[0]
    folder = ROOT/'assets/generated/meshy'/piece
    previous = folder/f'motion/runtime/v{args.previous}'
    source = previous/f'{piece}_animation_source.blend'
    out = folder/f'motion/runtime/v{args.version}'
    assert not out.exists(),out
    out.mkdir(parents=True)
    report = json.loads((previous/'runtime.json').read_text(encoding='utf-8'))
    report['sources'][str(source.relative_to(ROOT))] = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    body = next(o for o in bpy.context.scene.objects if o.type == 'MESH' and o.find_armature() == rig)
    ad = rig.animation_data; old_actions = {t.name:t.strips[0].action for t in ad.nla_tracks if t.strips}
    for track in list(ad.nla_tracks): ad.nla_tracks.remove(track)
    ad.action = None; rig.data.pose_position = 'REST'
    feet, top = elephant_rig(piece,rig,body) if family == 'elephant' else ({},0)
    # Equal-position seams must share weights before the runtime mesh is reduced.
    bm = bmesh.new(); bm.from_mesh(body.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
    bm.to_mesh(body.data); bm.free(); body.data.update()
    rig.data.pose_position = 'POSE'
    max_error = 0; clip_report = {}; sole_report = {}
    for name,old in old_actions.items():
        ad.action = old; ad.action_slot = old.slots[0]
        first,last = old.frame_range
        seconds = (last-first)/30
        if family == 'elephant' and name in ('walk','run'): seconds = 2.8 if name == 'walk' else 1.8
        count = round(seconds*30)
        samples = []; support_errors = []; clearance = []
        for frame in range(count+1):
            progress = frame/max(1,count)
            t = first+(last-first)*progress
            bpy.context.scene.frame_set(math.floor(t),subframe=t%1); bpy.context.view_layer.update()
            if family == 'horse':
                max_error = max(max_error,constrain_horse_hands(rig,piece))
            if family == 'elephant':
                # Replace the old whole-body stretch; the howdah stays rigid.
                for bone in rig.pose.bones:
                    if not bone.name.startswith('Native'):
                        bone.location = (0,0,0); bone.scale = (1,1,1); bone.rotation_mode = 'QUATERNION'; bone.rotation_quaternion = Quaternion()
                bpy.context.view_layer.update()
                motion = name in ('walk','run')
                if motion:
                    rig.pose.bones['Body'].location.z = -.004+.0015*math.sin(math.tau*progress*2)
                elif name == 'hit':
                    rig.pose.bones['Body'].location.y = .004*math.sin(math.pi*progress)
                bpy.context.view_layer.update()
                for prefix,d in feet.items():
                    phase = {('R','L'):0,('F','L'):.25,('R','R'):.5,('F','R'):.75}[(d['end'],d['side'])]
                    dy,dz,support = floor_cycle(progress,phase,.058 if piece.endswith('red') else .048,.026 if piece.endswith('red') else .022) if motion else (0,0,True)
                    target = d['foot']+Vector((0,dy,dz))
                    error = solve_chain(rig,prefix+'Upper',prefix+'Lower',prefix+'Foot',target,d['knee']+Vector((0,-.2 if d['end']=='F' else .2,0)),rig.data.bones[prefix+'Foot'].matrix_local.to_quaternion())
                    max_error = max(max_error,error)
                    if support: support_errors.append(error)
                    clearance.append(dz)
                head = rig.pose.bones['ElephantHead']; trunk = rig.pose.bones['ElephantTrunk']
                head.rotation_quaternion = Quaternion(Vector((1,0,0)),.012*math.sin(math.tau*progress))
                trunk.rotation_quaternion = Quaternion(Vector((0,1,0)),.025*math.sin(math.tau*progress))
                rig.pose.bones['ElephantTail'].rotation_quaternion = Quaternion(Vector((0,1,0)),.09*math.sin(math.tau*progress))
                bpy.context.view_layer.update()
            samples.append({b.name:(b.location.copy(),b.rotation_quaternion.copy() if b.rotation_mode=='QUATERNION' else b.rotation_euler.to_quaternion(),b.scale.copy()) for b in rig.pose.bones})
        if name in ('idle','walk','run'):
            # The first and final pose are identical; use a short closing blend
            # only for non-periodic native rider performance layered over gait.
            for index in range(max(1,len(samples)-8),len(samples)):
                t = smooth(len(samples)-9,len(samples)-1,index)
                for bone,(loc,rot,scale) in samples[index].items():
                    if bone.startswith('Native') or family != 'elephant':
                        a,b,c = samples[0][bone]
                        samples[index][bone] = (loc.lerp(a,t),rot.slerp(b,t),scale.lerp(c,t))
            samples[-1] = {bone:(loc.copy(),rot.copy(),scale.copy()) for bone,(loc,rot,scale) in samples[0].items()}
        result = bpy.data.actions.new(name+'_contacts'); ad.action = result
        for frame,pose in enumerate(samples):
            for bone,(loc,rot,scale) in pose.items():
                pb = rig.pose.bones[bone]; pb.rotation_mode = 'QUATERNION'; pb.location = loc; pb.rotation_quaternion = rot; pb.scale = scale
                for prop in ('location','rotation_quaternion','scale'): pb.keyframe_insert(data_path=prop,frame=frame,group=bone)
        for bag in curve_bags(result):
            for curve in bag.fcurves:
                for key in curve.keyframe_points: key.interpolation = 'LINEAR'
        ad.action = None; track = ad.nla_tracks.new(); track.name = name
        strip = track.strips.new(name,0,result); strip.action_slot = result.slots[0]; strip.extrapolation = 'NOTHING'; track.mute = True
        clip_report[name] = {'seconds':count/30,'native_rider_motion':report['clips'][name].get('native_rider_motion'),'local_contact_correction':True}
        if family == 'elephant': sole_report[name] = {'target_max_clearance_m':max(clearance),'support_joint_error_m':max(support_errors,default=0)}
    report['clips'] = clip_report
    report['contact_refinement'] = {'method':'analytic two-segment IK, original limb lengths, fixed support targets','max_joint_target_error_m':max_error,'elephant_feet':{n:{k:list(v) if isinstance(v,Vector) else v for k,v in d.items()} for n,d in feet.items()},'sole_targets':sole_report}
    report['review_clips'] = ['idle','walk'] if family == 'elephant' else ['idle']
    report['method'] += '; local hand contacts' if family == 'horse' else '; locally authored four-beat elephant gait with planted foot targets'
    report['files'] = {}
    rig.data.pose_position = 'REST'; bpy.context.scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/f'{piece}_animation_source.blend'),compress=True)
    if triangles(body)>20000:
        select(body); dec = body.modifiers.new('Runtime budget','DECIMATE'); dec.ratio = 19900/triangles(body)
        bpy.ops.object.modifier_move_up(modifier=dec.name); bpy.ops.object.modifier_apply(modifier=dec.name)
    body.data.validate(clean_customdata=False); body.data.update()
    for image in {n.image for mat in body.data.materials for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image}:
        if max(image.size)>2048: image.scale(2048,2048)
    rig.data.pose_position = 'POSE'; select(body); rig.select_set(True)
    path = out/f'{piece}_mobile.glb'
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_yup=True,export_image_format='WEBP',export_image_quality=95,export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_force_sampling=True,export_skins=True,export_def_bones=False)
    report['files']['mobile'] = {'file':path.name,'triangles':triangles(body),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    report['sources_unchanged'] = all(hashlib.sha256((ROOT/k).read_bytes()).hexdigest()==v for k,v in report['sources'].items()); assert report['sources_unchanged']
    (out/'runtime.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('NATIVE_CONTACTS',piece,'max_joint_error_m',max_error,'feet',sole_report,flush=True)


if __name__ == '__main__': main()
