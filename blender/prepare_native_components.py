"""Split original textured pieces into reviewable native-rig inputs and fixed equipment."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from build_humanoid_runtime import select
from build_vehicle_runtime import VehicleRig


def classify(piece, co, recipe=None):
    x, y, z = co
    red = piece.endswith('_red')
    if piece.startswith('elephant'):
        top = .156 if red else .112
        if z < top + .007:
            return 'pedestal'
        # The archer and bow are separated from the howdah, standards and canopy.
        if red:
            rider = -.100 < x < .108 and -.16 < y < -.018 and z > .823
            bow = -.143 < y < -.108 and -.09 < x < .12 and z > .845
        else:
            rider = -.067 < x < .070 and -.065 < y < .022 and z > .719
            bow = -.072 < y < -.044 and -.07 < x < .11 and z > .735
        if bow:
            return 'weapon'
        if rider:
            return 'rider'
        roof = .741 if red else .628
        if z > roof and y > (-.195 if red else -.24):
            return 'equipment'
        if red and z > .535 and abs(x) > .202 and -.12 < y < .26:
            return 'equipment'
        return 'animal'
    top = recipe.top
    if z < top + .007:
        return 'pedestal'
    weights = recipe.weights(co)
    strongest = max(weights, key=weights.get)
    if strongest == 'Weapon':
        return 'weapon'
    if piece.startswith('horse'):
        d = recipe.rider_info
        if (z > d['pelvis']+.005 and y > -.16) or (abs(x) > .106 and -.15 < y < .14 and z > (.385 if red else .30)):
            return 'rider'
        return 'animal'
    if piece.startswith('cannon'):
        if red and ((y < -.16 and z < .42) or (x > -.095 and z < .51)):
            return 'equipment'
        if strongest.startswith('Rider'):
            return 'rider'
        return 'equipment'
    raise ValueError(piece)


def add_hidden_leg_proxy(part, visible_bounds):
    """Use an existing Meshy human's legs below an occluded archer's waist.

    These helpers exist only in the rig upload. The original visible archer and
    its immutable assembly retain their exact geometry and textures.
    """
    source = ROOT/'assets/generated/meshy/cannon_red/native-input/v2/rider.glb'
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(source))
    added = set(bpy.data.objects)-before
    helper = next(o for o in added if o.type == 'MESH')
    helper.data.transform(helper.matrix_world); helper.parent = None; helper.matrix_world = Matrix.Identity(4)
    bm = bmesh.new(); bm.from_mesh(helper.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > .41], context='VERTS')
    scale = (visible_bounds[2][1]-visible_bounds[2][0])/.40
    cx = (visible_bounds[0][0]+visible_bounds[0][1])*.5
    cy = (visible_bounds[1][0]+visible_bounds[1][1])*.5
    for v in bm.verts:
        v.co = Vector((v.co.x*scale+cx, v.co.y*scale+cy, (v.co.z-.40)*scale+visible_bounds[2][0]+.025))
    bm.to_mesh(helper.data); bm.free(); helper.data.update()
    helper.data.materials.clear(); helper.data.materials.append(part.data.materials[0])
    for f in helper.data.polygons:
        f.material_index = 0
    select(part); helper.select_set(True); bpy.ops.object.join()
    for obj in added:
        if obj != helper and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    return {'source': str(source.relative_to(ROOT)), 'scale': scale, 'visible_min_z': visible_bounds[2][0]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pieces', required=True)
    p.add_argument('--version', type=int, default=1)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    jobs = []
    for piece in args.pieces.split(','):
        folder = ROOT / 'assets/generated/meshy' / piece
        source = folder / f'runtime/v1/{piece}_desktop.glb'
        out = folder / f'native-input/v{args.version}'
        if out.exists():
            raise RuntimeError(f'Input version already exists: {out}')
        out.mkdir(parents=True)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(source))
        mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
        mesh.data.transform(mesh.matrix_world)
        mesh.parent = None
        mesh.matrix_world = Matrix.Identity(4)
        mesh.data.update()
        recipe = None if piece.startswith('elephant') else VehicleRig(piece)
        if recipe:
            recipe.setup()
        roles = ('animal', 'rider', 'weapon', 'equipment', 'pedestal')
        parts = {}
        for role in roles:
            part = mesh.copy()
            part.data = mesh.data.copy()
            bpy.context.collection.objects.link(part)
            bm = bmesh.new()
            bm.from_mesh(part.data)
            removed = [f for f in bm.faces if classify(piece, f.calc_center_median(), recipe) != role]
            bmesh.ops.delete(bm, geom=removed, context='FACES')
            loose = [v for v in bm.verts if not v.link_faces]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context='VERTS')
            bm.to_mesh(part.data)
            bm.free()
            if not part.data.polygons:
                bpy.data.objects.remove(part, do_unlink=True)
                continue
            part.name = role
            part.data.update()
            parts[role] = part
        bpy.data.objects.remove(mesh, do_unlink=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'components.blend'), compress=True)
        report = {'piece': piece, 'source': str(source.relative_to(ROOT)), 'source_sha256': digest,
                  'source_unchanged': hashlib.sha256(source.read_bytes()).hexdigest() == digest, 'components': {}}
        for role, part in parts.items():
            coords = [v.co for v in part.data.vertices]
            bounds = [[min(v[i] for v in coords), max(v[i] for v in coords)] for i in range(3)]
            report['components'][role] = {'triangles': len(part.data.polygons), 'bounds': bounds}
            if role not in ('animal', 'rider'):
                continue
            if role == 'rider' and piece.startswith('elephant'):
                report['components'][role]['hidden_leg_proxy'] = add_hidden_leg_proxy(part, bounds)
                coords = [v.co for v in part.data.vertices]
                bounds = [[min(v[i] for v in coords), max(v[i] for v in coords)] for i in range(3)]
            # Upload centered, base-free input. Persist the exact inverse transform.
            offset = Vector(((bounds[0][0]+bounds[0][1])*.5, (bounds[1][0]+bounds[1][1])*.5, bounds[2][0]))
            for vertex in part.data.vertices:
                vertex.co -= offset
            part.data.update()
            # The visible assembly is saved above. Seal cut surfaces on the
            # upload proxy so missing saddle/sole surfaces do not confuse pose estimation.
            bm = bmesh.new()
            bm.from_mesh(part.data)
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.000001)
            boundary = [edge for edge in bm.edges if edge.is_boundary]
            if boundary:
                caps = bmesh.ops.holes_fill(bm, edges=boundary, sides=0)['faces']
                if caps:
                    bmesh.ops.triangulate(bm, faces=caps)
                bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            bm.to_mesh(part.data)
            bm.free()
            part.data.validate(clean_customdata=False)
            part.data.update()
            report['components'][role]['offset'] = list(offset)
            report['components'][role]['height'] = bounds[2][1]-bounds[2][0]
            for image in bpy.data.images:
                if image.type == 'IMAGE' and image.size[0]:
                    if max(image.size) > 2048:
                        image.scale(2048, 2048)
                    image.file_format = 'PNG'
                    image.pack()
            select(part)
            target = out / f'{role}.glb'
            bpy.ops.export_scene.gltf(filepath=str(target), export_format='GLB', use_selection=True,
                                      export_image_format='AUTO', export_yup=True, export_materials='EXPORT')
            for vertex in part.data.vertices:
                vertex.co += offset
            report['components'][role]['sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
            jobs.append({'piece': piece, 'role': role, 'operation': 'rig', 'version': args.version,
                         'model': str(target.relative_to(ROOT)).replace('\\', '/'),
                         'height': bounds[2][1]-bounds[2][0], 'skeleton': 'quadruped' if role == 'animal' else 'biped'})
        (out/'input.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('NATIVE_COMPONENTS', piece, {r: v['triangles'] for r, v in report['components'].items()}, flush=True)
    plan = ROOT / f'.meshy/native-components-{args.pieces.replace(",", "-")}-v{args.version}.json'
    plan.write_text(json.dumps({'jobs': jobs}, indent=2), encoding='utf-8')
    print('RIG_SPEC', plan, flush=True)


if __name__ == '__main__':
    main()
