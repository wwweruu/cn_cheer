"""Visual QA: six material tiles under overhead and grazing light."""
import bpy
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_meshy_sample import area, aim

root=Path(__file__).resolve().parents[1];output=root/'docs/asset-reports/environment';output.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
for i,key in enumerate(('ground_dirt','ground_stone','weathered_wood','aged_metal','fabric_red','fabric_black')):
    base=root/'assets/generated/meshy/scene'/key/'surface/v1/finished'
    material=bpy.data.materials.new(key);material.use_nodes=True;n=material.node_tree.nodes;l=material.node_tree.links;p=n.get('Principled BSDF')
    for channel in ('base_color','normal','orm'):
        tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(base/f'{channel}.png'))
        tex.image.colorspace_settings.name='sRGB' if channel=='base_color' else 'Non-Color'
        if channel=='base_color':l.new(tex.outputs['Color'],p.inputs['Base Color'])
        elif channel=='normal':
            normal=n.new('ShaderNodeNormalMap');l.new(tex.outputs['Color'],normal.inputs['Color']);l.new(normal.outputs['Normal'],p.inputs['Normal'])
        else:
            separate=n.new('ShaderNodeSeparateColor');l.new(tex.outputs['Color'],separate.inputs[0]);l.new(separate.outputs['Green'],p.inputs['Roughness']);l.new(separate.outputs['Blue'],p.inputs['Metallic'])
    bpy.ops.mesh.primitive_plane_add(size=2.8,location=((i%3-1)*3.15,(i//3-.5)*3.15,0));o=bpy.context.object;o.name=key;o.data.materials.append(material)
    for uv in o.data.uv_layers.active.data:uv.uv*=3
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
scene.cycles.device='GPU';world=bpy.data.worlds.new('QA neutral');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.08,.08,.08,1);world.node_tree.nodes['Background'].inputs[1].default_value=.4;scene.world=world
scene.render.resolution_x=1600;scene.render.resolution_y=1100;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX'
camera_data=bpy.data.cameras.new('QA camera');camera=bpy.data.objects.new('QA camera',camera_data);bpy.context.collection.objects.link(camera);scene.camera=camera;camera_data.type='ORTHO';camera_data.ortho_scale=10.8
area('Soft key',(0,-4,7),1500,6,(1,.97,.92),(0,0,0));key=bpy.data.objects['Soft key'];area('Fill',(4,2,4),350,4,(.8,.9,1),(0,0,0))
for name,position in (('overhead',(0,-.001,12)),('grazing',(0,-10,4.2))):
    camera.location=position;aim(camera,(0,0,0))
    if name=='grazing':key.location=(0,-7,1.4);aim(key,(0,0,0));key.data.energy=750
    scene.render.filepath=str(output/f'surfaces-{name}.png')
    if not Path(scene.render.filepath).exists():bpy.ops.render.render(write_still=True)
print('SURFACE_QA_RENDERED',flush=True)
