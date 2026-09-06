"""Create a textured, base-free humanoid derivative; keep the complete master intact."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--piece',required=True)
    parser.add_argument('--base-cut',type=float,default=.15);parser.add_argument('--version',type=int,default=1)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    assert args.piece.split('_')[0] in ('general','advisor','soldier')
    root=Path(__file__).resolve().parents[1];base=root/'assets/generated/meshy'/args.piece
    source=base/f'runtime/v1/{args.piece}_desktop.glb';out=base/f'rig-input/v{args.version}'
    assert not out.exists();out.mkdir(parents=True)
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(source))
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    heights=[]
    for obj in objects:
        world=obj.matrix_world.copy();obj.parent=None;obj.data.transform(world);obj.matrix_world=Matrix.Identity(4)
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.co.z<args.base_cut],context='VERTS')
        for v in bm.verts:v.co.z-=args.base_cut
        bm.to_mesh(obj.data);bm.free();obj.data.update()
        heights.extend(v.co.z for v in obj.data.vertices)
    assert heights and min(heights)>=-.001
    for image in bpy.data.images:
        if image.type!='IMAGE' or image.size[0]==0:continue
        if max(image.size)>2048:image.scale(2048,2048)
        image.file_format='PNG';image.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'body.blend'),compress=True)
    bpy.ops.export_scene.gltf(filepath=str(out/'model.glb'),export_format='GLB',export_image_format='AUTO',export_yup=True,export_materials='EXPORT')
    report={'piece':args.piece,'source':str(source),'source_sha256':source_hash,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==source_hash,
            'base_cut':args.base_cut,'height_meters':max(heights),'triangles':sum(len(p.vertices)-2 for o in objects for p in o.data.polygons),
            'body_glb_sha256':hashlib.sha256((out/'model.glb').read_bytes()).hexdigest(),
            'note':'Rig input only. The original complete base remains in the static master and will remain fixed in the animated derivative.'}
    (out/'input.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('RIG_INPUT',args.piece,report['triangles'],report['height_meters'],flush=True)


if __name__=='__main__':main()
