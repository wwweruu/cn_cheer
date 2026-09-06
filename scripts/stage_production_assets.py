"""Copy reviewed runtime derivatives to versioned public paths and inventory hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--require-complete',action='store_true');args=parser.parse_args()
    base=ROOT/'assets/generated/meshy';public=ROOT/'public/assets';report={'files':[],'missing':[]}
    pieces=[f'{kind}_{camp}' for kind in ('general','advisor','elephant','horse','chariot','cannon','soldier') for camp in ('red','black')]
    tasks=[]
    for asset in pieces:
        for tier in ('desktop','mobile','distant'):
            runtime=base/asset/'runtime'
            plain=runtime/'distant-webp-1k/model.glb' if tier=='distant' else runtime/'v1'/f'{asset}_{tier}.glb'
            target=public/'models/production'/asset
            tasks.extend([(plain,target/f'{tier}.webp.glb'),(runtime/'ktx-v1'/f'{asset}_{tier}.glb',target/f'{tier}.glb')])
    for asset in ('board_main','camp_red','camp_black','watchtower'):
        runtime=base/'scene'/asset/'runtime';target=public/'board/production'/asset
        for tier in ('desktop','mobile'):
            plain=runtime/f'rebaked-{tier}-v1/model.glb' if asset=='board_main' else runtime/'v1'/f'{asset}_{tier}.glb'
            ktx=runtime/('ktx-v2' if asset=='board_main' else 'ktx-v1')/f'{asset}_{tier}.glb'
            tasks.extend([(plain,target/f'{tier}.webp.glb'),(ktx,target/f'{tier}.glb')])
    for asset in ('ground_dirt','ground_stone','weathered_wood','aged_metal','fabric_red','fabric_black','battlefield_earth'):
        runtime=base/'scene'/asset/'surface/v1/finished/runtime';target=public/'environment/materials'/asset
        for tier in ('desktop','mobile'):
            tasks.extend([(runtime/f'{asset}_{tier}.glb',target/f'{tier}.webp.glb'),(runtime/'ktx-v1'/f'{asset}_{tier}.glb',target/f'{tier}.glb')])
    for source,target in tasks:
        if not source.exists():report['missing'].append(str(source.relative_to(ROOT)));continue
        raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        report['files'].append({'source':str(source.relative_to(ROOT)),'path':'/'+str(target.relative_to(ROOT/'public')).replace('\\','/'),'bytes':len(raw),'sha256':digest})
    path=public/'production-manifest.json';path.write_text(json.dumps(report,indent=2),encoding='utf8')
    for asset in pieces:
        runtime=json.loads((base/asset/'runtime/v1/runtime.json').read_text('utf8'))
        variants={}
        for label,tier in (('desktop','desktop'),('mobile','mobile'),('lod2','distant')):
            model=public/'models/production'/asset/f'{tier}.glb'
            if not model.exists():continue
            with model.open('rb') as stream:
                header=stream.read(20);document=json.loads(stream.read(struct.unpack_from('<I',header,12)[0]))
            triangles=sum(document['accessors'][p['indices']]['count']//3 for m in document['meshes'] for p in m['primitives'])
            variants[label]={'file':'/'+str(model.relative_to(ROOT/'public')).replace('\\','/'),'bytes':model.stat().st_size,
                             'triangles':triangles}
        gallery=public/'review/production'/asset;gallery.mkdir(parents=True,exist_ok=True)
        (gallery/'manifest.json').write_text(json.dumps({'variants':variants},indent=2),encoding='utf8')
    print('Staged',len(report['files']),'files; remaining',len(report['missing']),flush=True)
    if args.require_complete:assert not report['missing'],report['missing']


if __name__=='__main__':main()
