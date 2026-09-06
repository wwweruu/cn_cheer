"""Render actual model poses for visual review, without changing source assets."""
import argparse
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--clip')
    p.add_argument('--frames', default='0,20,40,60')
    p.add_argument('--views', default='front,side')
    p.add_argument('--material-source')
    p.add_argument('--size', type=int, default=560)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    source, out = ROOT / args.input, ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if source.suffix == '.blend':
        bpy.ops.wm.open_mainfile(filepath=str(source))
    elif source.suffix == '.fbx':
        bpy.ops.import_scene.fbx(filepath=str(source))
    else:
        bpy.ops.import_scene.gltf(filepath=str(source))
    bodies = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_render]
    skinned = [o for o in bodies if o.find_armature()]
    if skinned:
        bodies = skinned
    if args.material_source:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(ROOT/args.material_source))
        added = set(bpy.data.objects)-before
        material = next(o for o in added if o.type == 'MESH').data.materials[0]
        for body in bodies:
            body.data.materials.clear()
            body.data.materials.append(material)
            for polygon in body.data.polygons:
                polygon.material_index = 0
        for obj in added:
            bpy.data.objects.remove(obj, do_unlink=True)
    action_report = []
    for rig in [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']:
        rig.data.pose_position = 'POSE'
        ad = rig.animation_data
        if not ad:
            continue
        actions = [t.strips[0].action for t in ad.nla_tracks if t.strips]
        if ad.action:
            actions.insert(0, ad.action)
        for track in ad.nla_tracks:
            track.mute = True
        action = next((a for a in actions if args.clip and args.clip in a.name), actions[0] if actions else None)
        if action:
            ad.action = action
            ad.action_slot = action.slots[0]
        action_report.append({'rig': rig.name, 'bones': len(rig.data.bones), 'actions': [a.name for a in actions],
                              'selected': action.name if action else None, 'frames': list(action.frame_range) if action else None})
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 12
    scene.cycles.use_denoising = True
    scene.render.resolution_x = args.size
    scene.render.resolution_y = args.size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.world = bpy.data.worlds.new('Review world')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.42, .45, .5, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .7
    scene.view_settings.view_transform = 'AgX'
    camera_data = bpy.data.cameras.new('Review camera')
    camera = bpy.data.objects.new('Review camera', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = 'ORTHO'
    frames = [int(v) for v in args.frames.split(',')]
    bounds_report = []
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        points = []
        for body in bodies:
            obj = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
            evaluated = obj.to_mesh()
            points.extend(obj.matrix_world @ v.co for v in evaluated.vertices)
            obj.to_mesh_clear()
        bounds = [[min(v[i] for v in points), max(v[i] for v in points)] for i in range(3)]
        center = Vector([(lo+hi)*.5 for lo, hi in bounds])
        extent = max(hi-lo for lo, hi in bounds)
        bounds_report.append({'frame': frame, 'bounds': bounds})
        camera_data.ortho_scale = extent*1.22
        for view in args.views.split(','):
            direction = Vector({'front': (0, -3, .4), 'side': (3, 0, .4), 'quarter': (2, -3, 1)}[view])
            camera.location = center+direction*extent
            camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = str(out/f'{view}-{frame:03d}.png')
            bpy.ops.render.render(write_still=True)
    (out/'review.json').write_text(json.dumps({'source': str(source), 'rigs': action_report, 'poses': bounds_report}, indent=2))
    print('POSE_REVIEW', out, action_report, flush=True)


if __name__ == '__main__':
    main()
