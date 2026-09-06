"""Render API motion samples without changing source files or reposing their rig."""
import argparse
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_meshy_sample import aim, area

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--piece',default='soldier_red');parser.add_argument('--runtime',action='store_true');parser.add_argument('--runtime-version',type=int,default=1);parser.add_argument('--clips',default='idle,attack,hit,death');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    root=Path(__file__).resolve().parents[1];folder=root/'assets/generated/meshy'/args.piece/'motion';out=folder/(f'review-runtime-v{args.runtime_version}' if args.runtime else 'review');out.mkdir(exist_ok=True)
    report={}
    for clip in args.clips.split(','):
        source=folder/f'runtime/v{args.runtime_version}/{args.piece}_desktop.glb' if args.runtime else folder/clip/'v1/model.glb'
        bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(source))
        if args.runtime:
            for obj in bpy.context.scene.objects:
                if obj.type=='ARMATURE':
                    for track in obj.animation_data.nla_tracks:track.mute=True
                    action=bpy.data.actions[clip];obj.animation_data.action=action;obj.animation_data.action_slot=action.slots[0]
        scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
        preferences=bpy.context.preferences.addons['cycles'].preferences;preferences.compute_device_type='OPTIX';preferences.get_devices()
        for device in preferences.devices:device.use=device.type=='OPTIX'
        scene.cycles.device='GPU';scene.render.resolution_x=480;scene.render.resolution_y=540;scene.render.resolution_percentage=100
        scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
        world=bpy.data.worlds.new('World');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.04,.05,.065,1);world.node_tree.nodes['Background'].inputs[1].default_value=.4;scene.world=world
        actors=[o for o in scene.objects if o.type=='MESH' and not o.hide_render]
        actions=[bpy.data.actions[clip]] if args.runtime else list(bpy.data.actions);end=max(a.frame_range[1] for a in actions);start=min(a.frame_range[0] for a in actions)
        bpy.ops.mesh.primitive_plane_add(size=200);floor=bpy.context.object;floor.location.z=-.02
        mat=bpy.data.materials.new('floor');mat.diffuse_color=(.15,.17,.19,1);floor.data.materials.append(mat)
        area('Key',(-3,-4,5),600,3,(1,.96,.91),(0,0,.7));area('Fill',(3,-2,3),260,3,(.8,.9,1),(0,0,.7));area('Rim',(1,3,4),400,2,(1,1,1),(0,0,.7))
        camera_data=bpy.data.cameras.new('camera');camera=bpy.data.objects.new('camera',camera_data);bpy.context.collection.objects.link(camera);scene.camera=camera;camera.location=(1,-4,1.1);camera_data.type='ORTHO';camera_data.ortho_scale=2.7;aim(camera,(0,0,.6))
        samples=[]
        for index,fraction in enumerate((0,.25,.5,.75,1)):
            scene.frame_set(round(start+(end-start)*fraction));bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
            points=[o.evaluated_get(deps).matrix_world@Vector(c) for o in actors for c in o.evaluated_get(deps).bound_box]
            samples.append({'frame':scene.frame_current,'min':[min(p[i] for p in points) for i in range(3)],'max':[max(p[i] for p in points) for i in range(3)]})
            scene.render.filepath=str(out/f'{clip}-{index}.png');bpy.ops.render.render(write_still=True)
        report[clip]={'start':start,'end':end,'fps':scene.render.fps,'samples':samples}
        print('REVIEWED',clip,flush=True)
    (out/'motion.json').write_text(json.dumps(report,indent=2),encoding='utf8')

if __name__=='__main__':main()
