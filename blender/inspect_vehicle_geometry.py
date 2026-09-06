"""Read-only geometry measurements and colored orthographic QA data."""
import bpy,json,sys,collections
import numpy as np
from mathutils import Matrix
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
pieces=sys.argv[sys.argv.index('--')+1:]
for piece in pieces:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/'assets/generated/meshy'/piece/f'runtime/v1/{piece}_desktop.glb'))
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH');mesh.data.transform(mesh.matrix_world);mesh.parent=None;mesh.matrix_world=Matrix.Identity(4);mesh.data.update()
    mat=mesh.data.materials[0];shader=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    node=shader.inputs['Base Color'].links[0].from_node;image=node.image
    pixels=np.empty(image.size[0]*image.size[1]*4,dtype=np.float32);image.pixels.foreach_get(pixels);pixels=pixels.reshape(image.size[1],image.size[0],4)
    uv=mesh.data.uv_layers.active;colors=[];hist=collections.defaultdict(float)
    for f in mesh.data.polygons:
        coords=[uv.data[i].uv for i in f.loop_indices];u=sum(c.x for c in coords)/len(coords);v=sum(c.y for c in coords)/len(coords)
        rgba=pixels[round((v%1)*(image.size[1]-1)),round((u%1)*(image.size[0]-1))]
        colors.append([round(float(x)*255) for x in np.clip(rgba[:3],0,1)])
        if f.normal.z>.8 and f.center.z<.3:hist[round(f.center.z/.002)*.002]+=f.area
    data={'piece':piece,'vertices':[list(v.co) for v in mesh.data.vertices],'faces':[list(f.vertices) for f in mesh.data.polygons],'colors':colors,
        'bbox':[[min(v.co[i] for v in mesh.data.vertices),max(v.co[i] for v in mesh.data.vertices)] for i in range(3)],'top_areas':sorted(hist.items(),key=lambda p:-p[1])[:10]}
    out=ROOT/'.meshy/vehicle-rig';out.mkdir(exist_ok=True);(out/f'{piece}.json').write_text(json.dumps(data))
    print('MEASURED',piece,data['bbox'],data['top_areas'][:3],flush=True)
