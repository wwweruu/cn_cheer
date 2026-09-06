"""Verify shipped bytes/PBR, inventory source projects, and export a safe ledger."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/asset-reports'
BASE = ROOT / 'assets/generated/meshy'


def read(path):
    return json.loads(path.read_text('utf8'))


def relative(path):
    return str(path.resolve().relative_to(ROOT)).replace('\\', '/')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def glb(path):
    raw = path.read_bytes()
    assert raw[:4] == b'glTF'
    length = struct.unpack_from('<I', raw, 12)[0]
    doc = json.loads(raw[20:20+length])
    binary = memoryview(raw)[28+length:]
    images = []
    for image in doc.get('images', []):
        view = doc['bufferViews'][image['bufferView']]
        start = view.get('byteOffset', 0)
        data = binary[start:start+view['byteLength']]
        if image['mimeType'] == 'image/ktx2':
            assert bytes(data[:12]) == b'\xabKTX 20\xbb\r\n\x1a\n'
            width, height = struct.unpack_from('<II', data, 20)
            mips = struct.unpack_from('<I', data, 40)[0]
            assert mips == int(np.log2(max(width, height)))+1
            images.append({'size': [width, height], 'mips': mips, 'format': 'KTX2'})
        else:
            with Image.open(io.BytesIO(data)) as pixels:
                images.append({'size': list(pixels.size), 'format': pixels.format})
    triangles = sum(doc['accessors'][p['indices']]['count']//3 for m in doc['meshes'] for p in m['primitives'])
    geometry = hashlib.sha256()
    for accessor in doc['accessors']:
        view = doc['bufferViews'][accessor['bufferView']]
        start = view.get('byteOffset', 0)
        geometry.update(binary[start:start+view['byteLength']])
    for material in doc['materials']:
        pbr = material['pbrMetallicRoughness']
        assert pbr.get('baseColorTexture') is not None and pbr.get('metallicRoughnessTexture') is not None
        assert material.get('normalTexture') is not None
    return {'triangles': triangles, 'images': images, 'geometry_sha256': geometry.hexdigest()}


def sky_edges():
    path = ROOT/'public/assets/environment/atmosphere'
    ids = ['px', 'nx', 'py', 'ny', 'pz', 'nz']
    vector = [lambda u,v:(1,-v,-u),lambda u,v:(-1,-v,u),lambda u,v:(u,1,v),
              lambda u,v:(u,-1,-v),lambda u,v:(u,-v,1),lambda u,v:(-u,-v,-1)]
    sides = [('left',(-1,-1),(-1,1)),('right',(1,-1),(1,1)),('top',(-1,-1),(1,-1)),('bottom',(-1,1),(1,1))]
    edges = defaultdict(list)
    for face, name in enumerate(ids):
        pixels = np.asarray(Image.open(path/f'sky_{name}.webp').convert('RGB'), dtype=np.int16)
        for edge, a, b in sides:
            endpoints = [vector[face](*a), vector[face](*b)]
            values = {'left':pixels[:,0], 'right':pixels[:,-1], 'top':pixels[0], 'bottom':pixels[-1]}[edge]
            if endpoints[0] > endpoints[1]:
                endpoints.reverse(); values = values[::-1]
            edges[tuple(endpoints)].append((name+'_'+edge, values))
    assert len(edges) == 12
    result = []
    for pair in edges.values():
        assert len(pair) == 2
        delta = np.abs(pair[0][1]-pair[1][1])
        item = {'faces':[p[0] for p in pair], 'mae_8bit':float(delta.mean()), 'max_8bit':int(delta.max())}
        assert item['mae_8bit'] < 3 and item['max_8bit'] < 30, item
        result.append(item)
    return result


def safe_job(job):
    fields = ['key','piece','variant','endpoint','fingerprint','params','model','images','estimate',
              'name','state','held_credits','task_id','reported_credits','price_mismatch','archived','files']
    result = {field:job[field] for field in fields if field in job}
    encoded = json.dumps(result)
    assert 'https://' not in encoded and 'data:image' not in encoded and 'Bearer ' not in encoded
    return result


def main():
    manifest = read(ROOT/'public/assets/production-manifest.json')
    assert len(manifest['files']) == 128 and not manifest['missing']
    motion_manifest=read(ROOT/'public/assets/motion-manifest.json')
    assert len(motion_manifest['files'])==84
    files = []
    for file in manifest['files']+motion_manifest['files']:
        path = ROOT/'public'/file['path'].lstrip('/')
        assert path.stat().st_size == file['bytes'] and sha(path) == file['sha256'], path
        details = glb(path)
        cap = 1024 if path.stem.startswith('distant') else 2048 if path.stem.startswith('mobile') else 4096
        assert all(max(image['size']) <= cap for image in details['images'])
        assert len(details['images']) == 3
        files.append({**file, **details})
    indexed = {file['path']:file for file in files}
    for file in files:
        if '.webp.glb' in file['path']:
            paired = indexed[file['path'].replace('.webp.glb','.glb')]
            assert paired['geometry_sha256'] == file['geometry_sha256']
    print('All 212 runtime GLBs: hashes, geometry/animation pairs, PBR and mipmaps passed', flush=True)

    pieces = []
    for kind in ('general','advisor','elephant','horse','chariot','cannon','soldier'):
        for camp in ('red','black'):
            asset = f'{kind}_{camp}'; base = BASE/asset
            runtime = read(base/'runtime/v1/runtime.json')
            master = Path(runtime['source']); preservation = read(master.parent/'geometry-preservation.json')
            assert preservation['entire_triangle_surface_preserved'] and not preservation['source_file_modified']
            assert sha(master) == runtime['source_sha256'] == preservation['textured']['sha256']
            source = Path(preservation['source']['file']); assert sha(source) == preservation['source']['sha256']
            blend = base/f'runtime/v1/{asset}_source.blend'; assert blend.exists()
            pieces.append({'asset':asset,'source':relative(source),'source_sha256':preservation['source']['sha256'],
                'master':relative(master),'master_sha256':runtime['source_sha256'],'master_triangles':runtime['source_triangles'],
                'entire_triangle_surface_preserved':True,'source_texture_sizes':runtime['source_images'],
                'source_project':relative(blend),'source_project_sha256':sha(blend),
                'geometry_report':relative(master.parent/'geometry-preservation.json'),
                'renders':relative(master.parent/'renders'),
                'runtime':[f for f in files if '/models/production/'+asset+'/' in f['path']]})
            print('Master verified:', asset, flush=True)
    scenes = []
    for asset in ('board_main','camp_red','camp_black','watchtower'):
        base = BASE/'scene'/asset; runtime = read(base/'runtime/v1/runtime.json')
        source = base/'geometry/v1/model.glb'; blend = base/f'runtime/v1/{asset}_source.blend'
        assert sha(source) == runtime['source_sha256'] and blend.exists()
        scenes.append({'asset':asset,'source':relative(source),'source_sha256':runtime['source_sha256'],
            'source_triangles':runtime['source_triangles'],'source_texture_sizes':runtime['source_images'],
            'source_project':relative(blend),'source_project_sha256':sha(blend),
            'runtime':[f for f in files if '/board/production/'+asset+'/' in f['path']]})
    surfaces = []
    for asset in ('ground_dirt','ground_stone','weathered_wood','aged_metal','fabric_red','fabric_black','battlefield_earth'):
        base = BASE/'scene'/asset/'surface/v1/finished'; report = read(base/'surface.json')
        for key, info in report['images'].items():
            assert sha(base/(key+'.png')) == info['output_sha256']
        surfaces.append({'asset':asset, 'source_maps':relative(base), 'report':report,
            'runtime':[f for f in files if '/environment/materials/'+asset+'/' in f['path']]})
    images = []
    for asset in ('board_main_ref','camp_red_ref','camp_black_ref','watchtower_ref','sky_px','sky_nx','sky_py',
                  'sky_ny','sky_pz','sky_nz','distant_mountains','distant_camp','fx_embers','fx_smoke'):
        version = 2 if asset.startswith(('distant_','fx_')) else 1
        path = BASE/'scene'/asset/f'image/v{version}/image.png'
        with Image.open(path) as im:
            item = {'asset':asset, 'source':relative(path),'sha256':sha(path),'native_size':list(im.size),'mode':im.mode}
        runtime = ROOT/'public/assets/environment/atmosphere'/f'{asset}.webp'
        if runtime.exists(): item.update(runtime=relative(runtime),runtime_sha256=sha(runtime))
        images.append(item)

    ledger = read(ROOT/'.meshy/live/ledger.json')
    jobs = [safe_job(job) for job in ledger['jobs'].values()]
    assert all(j['state']=='SUCCEEDED' and j['archived'] and not j['price_mismatch'] for j in jobs)
    total = sum(job['held_credits'] for job in jobs); assert total<=ledger['budget']
    stamp = datetime.now(timezone.utc).isoformat()
    balance=read(OUT/'balance.json')
    safe = {'timestamp_utc':stamp, 'spent':total, 'balance_verified':balance['credits'],'balance_timestamp_utc':balance['timestamp_utc'], 'budget':1800,'balance_floor':1200, 'jobs':jobs}
    (OUT/'ledger.json').write_text(json.dumps(safe,ensure_ascii=False,indent=2),encoding='utf8')
    seams = sky_edges()
    (OUT/'environment/sky-seams.json').write_text(json.dumps(seams,indent=2),encoding='utf8')
    animations=[]
    for asset,version in motion_manifest['versions'].items():
        folder=BASE/asset/f'motion/runtime/v{version}';motion=read(folder/'runtime.json');assert motion['sources_unchanged']
        for name,digest in motion['sources'].items():assert sha(ROOT/name)==digest
        blend=folder/f'{asset}_animation_source.blend';assert blend.exists()
        animations.append({'asset':asset,'source_project':relative(blend),'source_project_sha256':sha(blend),'report':motion,
            'runtime':[f for f in files if '/models/motion/'+asset+'/' in f['path']]})
    api_files=[]
    for job in ledger['jobs'].values():
        for name,info in job['files'].items():
            path=BASE/job['key']/name;assert path.stat().st_size==info['bytes'] and sha(path)==info['sha256']
            api_files.append({'path':relative(path),**info})
    (OUT/'api-archive.json').write_text(json.dumps({'count':len(api_files),'bytes':sum(f['bytes'] for f in api_files),'files':api_files},indent=2),encoding='utf8')
    report = {'timestamp_utc':stamp, 'counts':{'pieces':14,'archived_scene_models':4,'active_scene_models':3,'surfaces':7,'images':14,'animated_pieces':14,'animation_clips':84,'runtime_glbs':212},
        'runtime_total_bytes':sum(f['bytes'] for f in files),'runtime_ktx_bytes':sum(f['bytes'] for f in files if '.webp.glb' not in f['path']),
        'pieces':pieces,'scenes':scenes,'surfaces':surfaces,'images':images,'sky_edges':seams,'animations':animations,
        'battlefield':{'source_reference':'象棋3D参考图-备份/棋盘/C1-棋盘全景俯视图.jpg','implementation':'src/scene/BattlefieldTerrain.tsx','rejected_board':'board_main','wooden_board_used':False,'ninety_points_preserved':True},
        'limits':['Sky faces are native 1K; distant layers are 1376x768. Initial >=2K goal is unmet; no enlargement claimed.',
                  'Mobile measurements emulate Pixel 7 on the desktop RTX 4060; physical mobile acceptance is pending.']}
    (OUT/'production.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    source_index = {'projects':[{k:a[k] for k in ('asset','source_project','source_project_sha256')} for a in pieces+scenes],
                    'animation_projects':[{k:a[k] for k in ('asset','source_project','source_project_sha256')} for a in animations],
                    'surfaces':[{k:a[k] for k in ('asset','source_maps')} for a in surfaces],
                    'inventory':'docs/asset-reports/production.json'}
    (ROOT/'assets/source/production.json').write_text(json.dumps(source_index,ensure_ascii=False,indent=2),encoding='utf8')
    backup = ROOT/'.meshy/backups'/datetime.now().strftime('delivery-%Y%m%d-%H%M%S.zip'); backup.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as archive:
        for folder in (ROOT/'.meshy/live', ROOT/'docs/asset-reports'):
            for path in folder.rglob('*.json'): archive.write(path,relative(path))
        for path in (ROOT/'scripts/meshy').glob('*.json'): archive.write(path,relative(path))
        archive.write(ROOT/'assets/source/production.json','assets/source/production.json')
    print(json.dumps({'counts':report['counts'],'runtime_MiB':report['runtime_total_bytes']/1048576,
        'ktx_MiB':report['runtime_ktx_bytes']/1048576,'spent':total,'sky_worst_mae':max(s['mae_8bit'] for s in seams),
        'backup':relative(backup)},indent=2),flush=True)


if __name__ == '__main__':
    main()
