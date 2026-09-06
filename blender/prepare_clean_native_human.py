"""Create equipment-free Meshy rig inputs while retaining the visible original master."""
import bpy, bmesh, json, sys, argparse, hashlib
from pathlib import Path
from mathutils import Matrix, Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).parent))
from build_humanoid_runtime import select
from repair_humanoid_runtime import weapon

def main():
 p=argparse.ArgumentParser();p.add_argument('--piece',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);piece=a.piece
 folder=ROOT/'assets/generated/meshy'/piece;source=folder/'rig-input/v1/model.glb';old=json.loads((source.parent/'input.json').read_text(encoding='utf-8'))
 out=folder/'native-input/v2';assert not out.exists();out.mkdir(parents=True)
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(source));body=next(o for o in bpy.context.scene.objects if o.type=='MESH')
 body.data.transform(body.matrix_world);body.parent=None;body.matrix_world=Matrix.Identity(4)
 bm=bmesh.new();bm.from_mesh(body.data)
 removed=[f for f in bm.faces if weapon(piece, f.calc_center_median()+Vector((0,0,old['base_cut'])))]
 bmesh.ops.delete(bm,geom=removed,context='FACES');bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
 edges=[e for e in bm.edges if e.is_boundary]
 caps=bmesh.ops.holes_fill(bm,edges=edges,sides=0)['faces'] if edges else []
 if caps:bmesh.ops.triangulate(bm,faces=caps)
 bm.to_mesh(body.data);bm.free();body.data.validate(clean_customdata=False);body.data.update()
 for im in bpy.data.images:
  if im.type=='IMAGE' and im.size[0]:
   if max(im.size)>2048:im.scale(2048,2048)
   im.file_format='PNG';im.pack()
 target=out/'body.glb';select(body);bpy.ops.export_scene.gltf(filepath=str(target),export_format='GLB',use_selection=True,export_image_format='AUTO',export_yup=True)
 report={'piece':piece,'source':str(source.relative_to(ROOT)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'base_cut':old['base_cut'],'height':max(v.co.z for v in body.data.vertices)-min(v.co.z for v in body.data.vertices),'excluded_equipment_faces':len(removed),'input_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
 (out/'input.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 job=dict(piece=piece,role='body',operation='rig',version=2,model=str(target.relative_to(ROOT)).replace('\\','/'),height=report['height'],skeleton='biped')
 (ROOT/f'.meshy/native-clean-{piece}.json').write_text(json.dumps({'jobs':[job]},indent=2),encoding='utf-8');print('CLEAN_NATIVE_RIG',piece,report,flush=True)
if __name__=='__main__':main()
