"""Stage immutable animated derivatives and their verified KTX/WebP pairs."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PIECES=[f'{kind}_{camp}' for kind in ('general','advisor','elephant','horse','chariot','cannon','soldier') for camp in ('red','black')]
VERSIONS={piece:1 for piece in PIECES}
VERSIONS.update(soldier_red=6,soldier_black=11,general_red=2,general_black=4,advisor_red=4,advisor_black=2)
VERSIONS.update(horse_red=6,horse_black=4,chariot_red=6,chariot_black=4,cannon_red=6,cannon_black=7)

def stage(piece,tier,webp_only):
    version=VERSIONS[piece];folder=ROOT/'assets/generated/meshy'/piece/f'motion/runtime/v{version}'
    source=folder/f'{piece}_{tier}.glb';assert source.is_file(),source
    raw=source.read_bytes();doc=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
    assert len(doc.get('animations',[]))==6 and len(doc.get('skins',[]))==1
    assert set(a['name'] for a in doc['animations'])=={'idle','attack','hit','death','walk','run'}
    output=ROOT/'public/assets/models/motion'/piece;output.mkdir(exist_ok=True,parents=True)
    shutil.copy2(source,output/f'{tier}.webp.glb')
    if not webp_only:
        ktx=folder/'ktx'/f'{piece}_{tier}.glb';ktx.parent.mkdir(exist_ok=True)
        if not ktx.exists():
            result=subprocess.run([sys.executable,str(ROOT/'scripts/compress_glb_textures.py'),'--input',str(source),'--output',str(ktx),'--threads','3'],capture_output=True,text=True)
            if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        shutil.copy2(ktx,output/f'{tier}.glb')
    print('STAGED_MOTION',piece,tier,flush=True)
    return {'piece':piece,'tier':tier,'source_version':version,'clips':{a['name']:len(a['channels']) for a in doc['animations']},'files':{
      p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in output.glob(f'{tier}*.glb')}}

def main():
    p=argparse.ArgumentParser();p.add_argument('--assets',default=','.join(PIECES));p.add_argument('--webp-only',action='store_true');p.add_argument('--workers',type=int,default=2);args=p.parse_args()
    assets=args.assets.split(',');report=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs=[pool.submit(stage,piece,tier,args.webp_only) for piece in assets for tier in ('desktop','mobile','distant')]
        for job in as_completed(jobs):report.append(job.result())
    out=ROOT/'docs/asset-reports/motion';out.mkdir(exist_ok=True,parents=True)
    (out/('staging-webp.json' if args.webp_only else 'staging.json')).write_text(json.dumps(sorted(report,key=lambda r:(r['piece'],r['tier'])),indent=2),encoding='utf8')
    if not args.webp_only and set(assets)==set(PIECES):
        files=[]
        for piece in PIECES:
            variants={};version=VERSIONS[piece]
            for tier in ('desktop','mobile','distant'):
                folder=ROOT/'assets/generated/meshy'/piece/f'motion/runtime/v{version}'
                entry=next(r for r in report if r['piece']==piece and r['tier']==tier)
                for name,info in entry['files'].items():
                    source=folder/(f'{piece}_{tier}.glb' if '.webp.' in name else f'ktx/{piece}_{tier}.glb')
                    files.append({'source':str(source.relative_to(ROOT)).replace('\\','/'),'path':f'/assets/models/motion/{piece}/{name}',**info})
                raw=(folder/f'{piece}_{tier}.glb').read_bytes();doc=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
                variants['lod2' if tier=='distant' else tier]={'file':f'/assets/models/motion/{piece}/{tier}.glb','bytes':entry['files'][f'{tier}.glb']['bytes'],'triangles':sum(doc['accessors'][p['indices']]['count']//3 for m in doc['meshes'] for p in m['primitives'])}
            gallery=ROOT/'public/assets/review/motion'/piece;gallery.mkdir(exist_ok=True,parents=True)
            (gallery/'manifest.json').write_text(json.dumps({'variants':variants},indent=2),encoding='utf8')
        assert len(files)==84
        (ROOT/'public/assets/motion-manifest.json').write_text(json.dumps({'files':files,'versions':VERSIONS},indent=2),encoding='utf8')

if __name__=='__main__':main()
