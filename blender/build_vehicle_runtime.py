"""Anatomical mounted rigs and rigid machine articulation, built from static masters.

Blender coordinates: X right, -Y forward, Z up. All joints use world-aligned axes.
Attack release and contact match src/scene/moveTimeline.ts (0.356 and 0.593).
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
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).parent))
from repair_humanoid_runtime import split_at

ROOT = Path(__file__).resolve().parents[1]
TOPS = dict(horse_red=.118, horse_black=.078, chariot_red=.104,
            chariot_black=.063, cannon_red=.174, cannon_black=.122)
TAU = math.tau


def smooth(a, b, v):
    t = max(0, min(1, (v-a)/(b-a)))
    return t*t*(3-2*t)


def curve(p, keys):
    for (a, x), (b, y) in zip(keys, keys[1:]):
        if p <= b:
            return x+(y-x)*smooth(a, b, p)
    return keys[-1][1]


def blend(a, b, amount):
    return {a: 1-amount, b: amount}


def select(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def tris(obj):
    return sum(len(p.vertices)-2 for p in obj.data.polygons)


class VehicleRig:
    def __init__(self, piece):
        self.piece = piece
        self.family, self.camp = piece.split('_')
        self.red = self.camp == 'red'
        self.top = TOPS[piece]
        self.defs = {'FixedPedestal': ((0, 0, 0), None), 'Body': ((0, 0, self.top), 'FixedPedestal')}
        self.horses = []
        self.wheels = []

    def add(self, name, xyz, parent='Body'):
        self.defs[name] = (xyz, parent)

    def horse(self, prefix, x, hip, knee, fy, ry, neck, head, bodytop, width):
        self.add(prefix+'Back', (x, ry, hip))
        self.add(prefix+'Neck', (x, neck[0], neck[1]), prefix+'Back')
        self.add(prefix+'Head', (x, head[0], head[1]), prefix+'Neck')
        self.add(prefix+'Tail', (x, ry+.10, bodytop-.08), prefix+'Back')
        for end, y in [('F', fy), ('R', ry)]:
            for side, dx in [('L', -width), ('R', width)]:
                name = prefix+end+side
                self.add(name+'Upper', (x+dx, y, hip), prefix+'Back')
                self.add(name+'Lower', (x+dx, y, knee), name+'Upper')
        self.horses.append(dict(prefix=prefix, x=x, hip=hip, knee=knee, fy=fy, ry=ry,
                                neck=neck, head=head, bodytop=bodytop, width=width))

    def rider(self, x, y, pelvis, shoulder, hand, head, spread, parent='Body'):
        self.rider_info = dict(x=x, y=y, pelvis=pelvis, shoulder=shoulder, hand=hand, head=head, spread=spread)
        self.add('Rider', (x, y, pelvis), parent)
        self.add('RiderHead', (x, y, head), 'Rider')
        for side, sign in [('L', -1), ('R', 1)]:
            self.add('Rider'+side+'Arm', (x+sign*spread*.50, y, shoulder), 'Rider')
            self.add('Rider'+side+'Hand', (x+sign*spread*.78, y, (shoulder+hand)*.5), 'Rider'+side+'Arm')
        self.add('Weapon', (x-spread, y, hand), 'RiderLHand')
        self.add('RiderLFoot', (x-spread*.35, y, pelvis-.03))
        self.add('RiderRFoot', (x+spread*.35, y, pelvis-.03))

    def setup(self):
        r = self.red
        if self.family == 'horse':
            self.horse('Horse', 0, .43 if r else .34, .275 if r else .215,
                       -.145, .205 if r else .22, (-.19, .54 if r else .43),
                       (-.32, .66 if r else .56), .635 if r else .545, .057)
            self.rider(0, -.01 if r else -.035, .64 if r else .55, .82 if r else .71,
                       .715 if r else .633, .865 if r else .76, .203, 'HorseBack')
            self.weapon_xy = (-.203, -.014 if r else -.041)
        elif self.family == 'chariot':
            for n, x in [('LeftHorse', -.11 if r else -.10), ('RightHorse', .12 if r else .10)]:
                self.horse(n, x, .285 if r else .225, .19 if r else .145, -.295, -.035,
                           (-.28, .405 if r else .33), (-.38, .49 if r else .40), .44 if r else .36, .026)
            self.rider(0, .235 if r else .215, .55 if r else .455, .755 if r else .60,
                       .67 if r else .523, .765 if r else .59, .15 if r else .11)
            self.weapon_xy = (-.156 if r else -.108, .101 if r else .145)
            self.add('Canopy', (0, .235, .905 if r else .685))
            self.wheel_y, self.wheel_z, self.wheel_radius = (.164, .283, .182) if r else (.164, .235, .184)
            self.wheel_x = .275 if r else .24
            for side, sign in [('L', -1), ('R', 1)]:
                name = 'Wheel'+side
                self.add(name, (sign*self.wheel_x, self.wheel_y, self.wheel_z))
                self.wheels.append(name)
        elif r:
            self.rider(-.213, -.05, .56, .835, .625, .9, .16)
            self.weapon_xy = (-.373, -.10)
            self.add('Barrel', (.143, .10, .676))
            self.barrel_start = Vector((.143, -.16, .52))
            self.barrel_end = Vector((.143, .405, .858))
            self.barrel_axis = (self.barrel_end-self.barrel_start).normalized()
            self.add('Muzzle', tuple(self.barrel_end), 'Barrel')
            for name, x in [('WheelL', -.012), ('WheelR', .34)]:
                self.add(name, (x, .036, .383))
                self.wheels.append(name)
        else:
            self.rider(-.33, .03, .32, .495, .36, .535, .102)
            self.weapon_xy = (-.422, .061)
            self.add('ThrowArm', (0, 0, .80))
            self.add('Counterweight', (0, 0, .55))
            self.add('Winch', (0, -.045, .245))
            self.add('Muzzle', (0, .008, 1.245), 'ThrowArm')

    def rider_weights(self, co):
        x, y, z = co
        d = self.rider_info
        dx = x-d['x']
        side = 'L' if dx < 0 else 'R'
        if z > d['head']:
            return blend('Rider', 'RiderHead', smooth(d['head'], d['head']+.035, z))
        amount = smooth(d['spread']*.38, d['spread']*.73, abs(dx))*smooth(d['pelvis'], d['hand'], z)
        hand = 1-smooth(d['hand']+.015, (d['shoulder']+d['hand'])*.5+.025, z)
        return {'Rider': 1-amount, 'Rider'+side+'Arm': amount*(1-hand), 'Rider'+side+'Hand': amount*hand}

    def horse_weights(self, h, co):
        x, y, z = co
        pre, hip, knee = h['prefix'], h['hip'], h['knee']
        if y > h['ry']+.095 and z < h['bodytop']-.025:
            return blend(pre+'Back', pre+'Tail', smooth(h['ry']+.095, h['ry']+.15, y))
        if z < hip+.05:
            end = 'F' if abs(y-h['fy']) < abs(y-h['ry']) else 'R'
            side = 'L' if x < h['x'] else 'R'
            amount = 1-smooth(hip-.025, hip+.055, z)
            lower = 1-smooth(knee-.025, knee+.035, z)
            name = pre+end+side
            return {pre+'Back': 1-amount, name+'Upper': amount*(1-lower), name+'Lower': amount*lower}
        neck = smooth(-h['neck'][0]-.045, -h['neck'][0]+.05, -y)*smooth(hip, hip+.12, z)
        head = smooth(-h['head'][0]-.025, -h['head'][0]+.055, -y)
        return {pre+'Back': 1-neck, pre+'Neck': neck*(1-head), pre+'Head': neck*head}

    def weights(self, co):
        x, y, z = co
        wx, wy = self.weapon_xy
        if self.family in ('horse', 'chariot'):
            # Shaft, metal tip and tassel all remain a single rigid object.
            radius = .045 if z > self.rider_info['hand']+.055 else .021
            if self.family == 'chariot' and abs(z-(.926 if self.red else .71)) < .042:
                radius = .008
            if math.hypot(x-wx, y-wy) < radius:
                return {'Weapon': 1}
        elif math.hypot(x-wx, y-wy) < .020 and z < self.rider_info['hand']+.018:
            return {'Weapon': 1}
        if self.family == 'horse':
            if z > self.rider_info['pelvis']+.015 and y > -.16:
                return self.rider_weights(co)
            # Rider boots and skirts outside the horse's flanks stay on the saddle.
            if abs(x) > .115 and -.15 < y < .14 and z > (.385 if self.red else .30):
                return {'HorseBack': 1}
            return self.horse_weights(self.horses[0], co)
        if self.family == 'chariot':
            if abs(x) > self.wheel_x-.023 and math.hypot(y-self.wheel_y, z-self.wheel_z) < self.wheel_radius:
                return {'WheelL' if x < 0 else 'WheelR': 1}
            if z > (.855 if self.red else .655):
                return {'Canopy': 1}
            if y > .02 and z > self.rider_info['pelvis']+.005:
                return self.rider_weights(co)
            if y < .02 and z < (.62 if self.red else .50):
                h = min(self.horses, key=lambda h: abs(x-h['x']))
                weights = self.horse_weights(h, co)
                amount = 1-smooth(-.07, .02, y)
                return {**{name: value*amount for name, value in weights.items()}, 'Body': 1-amount}
            return {'Body': 1}
        if self.red:
            if y < -.17 and z < .325:
                return {'Body': 1}
            delta = Vector(co)-self.barrel_start
            along = delta.dot(self.barrel_axis)
            radial = (delta-self.barrel_axis*along).length
            if -.065 < along < .71 and radial < .090 and z > .45:
                return {'Barrel': 1}
            for name, wx in [('WheelL', -.012), ('WheelR', .34)]:
                if abs(x-wx) < .028 and math.hypot(y-.036, z-.383) < .213:
                    return {name: 1}
            if x < -.045 and z > .18:
                if z < .51:
                    side = 'L' if x < -.213 else 'R'
                    return blend('Rider', 'Rider'+side+'Foot', 1-smooth(.39, .53, z))
                return self.rider_weights(co)
            return {'Body': 1}
        if x < -.215 and z > .14:
            if z < .285:
                side = 'L' if x < -.33 else 'R'
                return blend('Rider', 'Rider'+side+'Foot', 1-smooth(.25, .32, z))
            return self.rider_weights(co)
        if z > .842 or (abs(x) < .04 and abs(y) < .05 and z > .80):
            return {'ThrowArm': 1}
        if -.112 < x < .120 and -.167 < y < .171 and .345 < z < .548:
            return {'Counterweight': 1}
        if abs(x) < .105 and abs(y+.045) < .09 and .212 < z < .279:
            return {'Winch': 1}
        return {'Body': 1}

    def pose(self, rig, name, p):
        b = rig.pose.bones
        for bone in b:
            bone.rotation_mode = 'XYZ'
            bone.location = (0, 0, 0)
            bone.rotation_euler = (0, 0, 0)
            bone.scale = (1, 1, 1)
        s = math.sin(TAU*p)
        if name == 'idle':
            b['RiderHead'].rotation_euler.z = .11*s
            b['RiderLArm'].rotation_euler.x = .025*s
            b['RiderRArm'].rotation_euler.x = -.035*s
            for h in self.horses:
                pre = h['prefix']
                b[pre+'Neck'].rotation_euler.x = .055*s
                b[pre+'Head'].rotation_euler.z = .055*math.sin(TAU*p)
                b[pre+'Tail'].rotation_euler.y = .20*math.sin(TAU*p)
            if self.wheels and self.family == 'chariot':
                b['Canopy'].rotation_euler.y = .024*s
            if self.family == 'cannon' and not self.red:
                b['Winch'].rotation_euler.x = .12*s
        elif name in ('walk', 'run'):
            fast = name == 'run'
            cycles = 2 if fast else 1
            phase = TAU*p*cycles
            for hi, h in enumerate(self.horses):
                pre = h['prefix']
                b[pre+'Back'].location.z = .006*(1-math.cos(phase*2))
                b[pre+'Neck'].rotation_euler.x = .08*math.sin(phase)
                b[pre+'Tail'].rotation_euler.y = .27*math.sin(phase)
                for end in ('F', 'R'):
                    for side in ('L', 'R'):
                        diagonal = 0 if (end == 'F') == (side == 'L') else math.pi
                        wave = math.sin(phase+diagonal+hi*.45)
                        leg = pre+end+side
                        b[leg+'Upper'].rotation_euler.x = (.38 if fast else .26)*wave
                        b[leg+'Lower'].rotation_euler.x = -.58*max(0, wave)
            for wheel in self.wheels:
                b[wheel].rotation_euler.x = -TAU*p*(2 if fast else 1)
            b['Rider'].rotation_euler.x = .035*math.sin(phase*2)
            b['RiderLArm'].rotation_euler.x = .075*math.sin(phase)
            b['RiderRArm'].rotation_euler.x = -.075*math.sin(phase)
            if self.family == 'cannon':
                for side, ph in [('L', 0), ('R', math.pi)]:
                    b['Rider'+side+'Foot'].rotation_euler.x = .20*math.sin(phase+ph)
            if self.family == 'chariot':
                b['Canopy'].rotation_euler.y = .045*math.sin(phase)
        elif name == 'attack':
            ready = curve(p, [(0, 0), (.24, 1), (.45, 0), (1, 0)])
            impact = curve(p, [(0, 0), (.32, 0), (.593, 1), (.78, .3), (1, 0)])
            if self.family in ('horse', 'chariot'):
                for h in self.horses:
                    pre = h['prefix']
                    rear = .25 if self.family == 'horse' else .07
                    b[pre+'Back'].rotation_euler.x = -rear*ready+.065*impact
                    b[pre+'Back'].location.z = .015*impact
                    b[pre+'Neck'].rotation_euler.x = -.12*ready+.19*impact
                    b[pre+'Head'].rotation_euler.x = -.07*impact
                    b[pre+'Tail'].rotation_euler.y = .28*ready
                    for side in ('L', 'R'):
                        b[pre+'F'+side+'Upper'].rotation_euler.x = -.30*ready
                        b[pre+'F'+side+'Lower'].rotation_euler.x = -.46*ready
                b['Rider'].rotation_euler.x = -.10*ready+.14*impact
                b['RiderLArm'].rotation_euler.x = -.14*ready+.65*impact
                b['RiderLHand'].rotation_euler.x = .15*impact
                b['Weapon'].rotation_euler.x = .28*impact
                b['RiderRArm'].rotation_euler.x = .20*impact
                for wheel in self.wheels:
                    b[wheel].rotation_euler.x = -.85*impact
                if self.family == 'chariot':
                    b['Canopy'].rotation_euler.x = -.065*impact
            else:
                recoil = curve(p, [(0, 0), (.35556, 0), (.405, 1), (.49, .65), (.78, 0), (1, 0)])
                b['Rider'].rotation_euler.x = -.13*recoil
                b['RiderLArm'].rotation_euler.x = .48*ready-.15*recoil
                b['RiderRArm'].rotation_euler.x = .35*ready-.25*recoil
                b['RiderHead'].rotation_euler.z = -.18*ready
                if self.red:
                    b['Barrel'].location = -self.barrel_axis*.085*recoil
                    b['Weapon'].rotation_euler.x = -.22*ready
                else:
                    swing = curve(p, [(0, 0), (.235, -.82), (.28, -.82), (.35556, .50), (.43, .72), (.56, .61), (.93, 0), (1, 0)])
                    b['ThrowArm'].rotation_euler.x = swing
                    b['Winch'].rotation_euler.x = -TAU*ready
        elif name == 'hit':
            hit = math.sin(math.pi*p)*(1-p)
            b['Rider'].rotation_euler.x = -.26*hit
            b['RiderHead'].rotation_euler.x = -.16*hit
            for h in self.horses:
                b[h['prefix']+'Neck'].rotation_euler.x = -.26*hit
                b[h['prefix']+'Head'].rotation_euler.z = .19*hit
            if self.family == 'cannon' and not self.red:
                b['ThrowArm'].rotation_euler.x = -.22*hit
            if self.family == 'chariot':
                b['Canopy'].rotation_euler.y = .14*hit
        elif name == 'death':
            fall = smooth(.03, .80, p)
            b['Rider'].rotation_euler.x = .39*fall
            b['RiderHead'].rotation_euler.x = .22*fall
            b['RiderLArm'].rotation_euler.x = .55*fall
            b['RiderRArm'].rotation_euler.x = .48*fall
            for h in self.horses:
                pre = h['prefix']
                b[pre+'Neck'].rotation_euler.x = .34*fall
                b[pre+'Head'].rotation_euler.x = .20*fall
                for end in ('F', 'R'):
                    for side in ('L', 'R'):
                        b[pre+end+side+'Upper'].rotation_euler.x = -.34*fall
                        b[pre+end+side+'Lower'].rotation_euler.x = .68*fall
            if self.family == 'chariot':
                b['Canopy'].rotation_euler.y = .18*fall
            elif self.family == 'cannon':
                if self.red:
                    b['Barrel'].rotation_euler.x = -.15*fall
                else:
                    b['ThrowArm'].rotation_euler.x = -.65*fall


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--piece', required=True, choices=TOPS)
    parser.add_argument('--version', type=int, default=2)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    recipe = VehicleRig(args.piece)
    recipe.setup()
    folder = ROOT/'assets/generated/meshy'/args.piece
    out = folder/f'motion/runtime/v{args.version}'
    assert not out.exists(), out
    out.mkdir(parents=True)
    source = folder/f'runtime/v1/{args.piece}_desktop.glb'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    body = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
    body.data.transform(body.matrix_world)
    body.parent = None
    body.matrix_world = Matrix.Identity(4)
    body.data.update()
    # Close contact cuts on both sides, preserving the original plate's texture.
    candidates = [f for f in body.data.polygons if f.normal.z > .9 and abs(f.center.z-recipe.top) < .008]
    sample = max(candidates, key=lambda f: f.area)
    uv_layer = body.data.uv_layers.active
    cap_uv = sum((uv_layer.data[i].uv for i in sample.loop_indices), Vector((0, 0)))/len(sample.loop_indices)
    base = body.copy()
    base.data = body.data.copy()
    bpy.context.collection.objects.link(base)
    # Scanned plates have raised rim/top noise above the dominant horizontal face.
    # Cut above that noise so no broad plate triangles enter moving foot weights.
    cut_height = recipe.top+(.014 if args.piece == 'cannon_red' else .009)
    base_caps = split_at(base, recipe.top-.0015, False, cap_uv)
    body_caps = split_at(body, cut_height+.0001, True, cap_uv)
    # Close the old contact footprints and bring the new soles to the plate.
    # This avoids leaving fixed hoof/weapon stumps when a component lifts.
    floor_height = recipe.top-.0012
    for vertex in body.data.vertices:
        vertex.co.z -= (cut_height+.0001-floor_height)*(1-smooth(cut_height, cut_height+.035, vertex.co.z))
    body.data.update()
    edge = [v.co for v in base.data.vertices if v.co.z > recipe.top-.006]
    cx = (max(v.x for v in edge)+min(v.x for v in edge))*.5
    cy = (max(v.y for v in edge)+min(v.y for v in edge))*.5
    rx = (max(v.x for v in edge)-min(v.x for v in edge))*.489
    ry = (max(v.y for v in edge)-min(v.y for v in edge))*.489
    bm = bmesh.new()
    bm.from_mesh(base.data)
    uv = bm.loops.layers.uv.active
    center = bm.verts.new((cx, cy, floor_height))
    rim = [bm.verts.new((cx+rx*math.cos(i*TAU/128), cy+ry*math.sin(i*TAU/128), floor_height)) for i in range(128)]
    for i in range(128):
        face = bm.faces.new((center, rim[i], rim[(i+1)%128]))
        for loop in face.loops:
            loop[uv].uv = cap_uv+Vector((loop.vert.co.x*.012, loop.vert.co.y*.012))
    bm.to_mesh(base.data)
    bm.free()
    base.data.update()
    data = bpy.data.armatures.new(args.piece+'_component_rig')
    rig = bpy.data.objects.new(data.name, data)
    bpy.context.collection.objects.link(rig)
    select(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (head, parent) in recipe.defs.items():
        bone = data.edit_bones.new(name)
        bone.head = head
        bone.tail = (head[0], head[1]+.06, head[2])
        if parent:
            bone.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    # Open the scan's artificial connections at moving rigid component seams.
    # Faces keep their original UVs and move rigidly as complete triangles.
    rigid = {'Weapon', 'WheelL', 'WheelR', 'Barrel', 'ThrowArm', 'Counterweight', 'Winch', 'Canopy'}
    bm = bmesh.new()
    bm.from_mesh(body.data)
    tags = bm.faces.layers.int.new('rigid_component')
    rigid_names = ['']+sorted(rigid)
    for face in bm.faces:
        weights = recipe.weights(face.calc_center_median())
        name = max(weights, key=weights.get)
        face[tags] = rigid_names.index(name) if name in rigid else 0
    edges = [edge for edge in bm.edges if any(face[tags] for face in edge.link_faces)]
    bmesh.ops.split_edges(bm, edges=edges)
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    rigid_vertices = {}
    attribute = body.data.attributes['rigid_component']
    for face in body.data.polygons:
        tag = attribute.data[face.index].value
        if tag:
            for index in face.vertices:
                rigid_vertices[index] = rigid_names[tag]
    groups = {name: body.vertex_groups.new(name=name) for name in recipe.defs}
    counts = Counter()
    for vertex in body.data.vertices:
        if vertex.index in rigid_vertices:
            weights = {rigid_vertices[vertex.index]: 1}
        else:
            weights = recipe.weights(vertex.co)
            # Seam vertices on the remaining body side cannot retain a rigid
            # region's weight; otherwise the boundary faces still stretch.
            for name in list(weights):
                if name in rigid:
                    fallback = 'RiderLHand' if name == 'Weapon' and vertex.co.z > recipe.rider_info['hand']-.05 else 'Body'
                    weights[fallback] = weights.get(fallback, 0)+weights.pop(name)
        for name, weight in weights.items():
            if weight > 1e-7:
                groups[name].add([vertex.index], weight, 'REPLACE')
                counts[name] += 1
    # Restore shared topology inside each rigid island before LOD decimation.
    # Only vertices controlled by exactly the same joint may be welded.
    bm = bmesh.new()
    bm.from_mesh(body.data)
    deform = bm.verts.layers.deform.active
    for name in rigid:
        if name not in groups:
            continue
        group_index = groups[name].index
        vertices = [v for v in bm.verts if v[deform].get(group_index, 0) > .999999]
        if vertices:
            bmesh.ops.remove_doubles(bm, verts=vertices, dist=.0000001)
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    base.vertex_groups.clear()
    base.vertex_groups.new(name='FixedPedestal').add(list(range(len(base.data.vertices))), 1, 'REPLACE')
    select(body)
    base.select_set(True)
    bpy.ops.object.join()
    body.name = args.piece+'_animated'
    body.parent = rig
    modifier = body.modifiers.new('Anatomical and rigid components', 'ARMATURE')
    modifier.object = rig
    scene = bpy.context.scene
    scene.render.fps = 30
    animation = rig.animation_data_create()
    clips = {}
    for name, duration in [('idle', 4), ('attack', 1.35), ('hit', .7), ('death', 1.6), ('walk', 1.2), ('run', .8)]:
        action = bpy.data.actions.new(name)
        animation.action = action
        frames = round(duration*30)
        for frame in range(frames+1):
            recipe.pose(rig, name, frame/frames)
            for bone in rig.pose.bones:
                for prop in ('location', 'rotation_euler'):
                    bone.keyframe_insert(data_path=prop, frame=frame, group=bone.name)
        action.use_fake_user = True
        track = animation.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name, 0, action)
        strip.action_slot = action.slots[0]
        strip.extrapolation = 'NOTHING'
        track.mute = True
        clips[name] = {'seconds': frames/30, 'frames': [0, frames]}
        animation.action = None
    recipe.pose(rig, 'idle', 0)
    scene.frame_set(0)
    rig.data.pose_position = 'REST'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/f'{args.piece}_animation_source.blend'), compress=True)
    report = {'piece': args.piece, 'api_rig': False, 'api_cost': 0, 'method': 'anatomical quadruped gait and separately articulated rigid machine components',
              'fixed_base_bone': 'FixedPedestal', 'base_surface': recipe.top, 'base_caps': base_caps, 'body_caps': body_caps,
              'joint_count': len(recipe.defs), 'weighted_vertices': dict(counts), 'clips': clips, 'files': {},
              'release_normalized': .35556, 'contact_normalized': .59259, 'sources': {str(source.relative_to(ROOT)): digest}}
    for tier, target, size in [('desktop', 60000, 4096), ('mobile', 20000, 2048), ('distant', 12000, 1024)]:
        rig.data.pose_position = 'REST'
        if tris(body) > target:
            select(body)
            dec = body.modifiers.new('Runtime budget', 'DECIMATE')
            dec.ratio = (target-100)/tris(body)
            bpy.ops.object.modifier_move_up(modifier=dec.name)
            bpy.ops.object.modifier_apply(modifier=dec.name)
            body.data.validate(clean_customdata=False)
        for material in body.data.materials:
            for im in {n.image for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image}:
                if max(im.size) > size:
                    im.scale(size, size)
        rig.data.pose_position = 'POSE'
        select(body)
        rig.select_set(True)
        path = out/f'{args.piece}_{tier}.glb'
        bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True, export_yup=True,
            export_image_format='WEBP', export_image_quality=95, export_materials='EXPORT', export_animations=True,
            export_animation_mode='NLA_TRACKS', export_frame_range=False, export_force_sampling=True, export_skins=True, export_def_bones=False)
        report['files'][tier] = {'file': path.name, 'triangles': tris(body), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        print('VEHICLE_MOTION', args.piece, tier, report['files'][tier], flush=True)
    report['sources_unchanged'] = hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert report['sources_unchanged']
    (out/'runtime.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
