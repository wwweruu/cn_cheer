"""Reuse only byte-identical source textures while packing the reviewed vehicle rigs."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
from stage_motion_assets import ROOT, VERSIONS

def compress(item):
    piece, tier = item
    parent = ROOT/'assets/generated/meshy'/piece/'motion/runtime'
    current = parent/f'v{VERSIONS[piece]}'
    name = f'{piece}_{tier}.glb'
    out = current/'ktx'/name
    out.parent.mkdir(exist_ok=True)
    if not out.exists():
        subprocess.run([sys.executable, str(ROOT/'scripts/compress_glb_textures.py'),
            '--input', str(current/name), '--output', str(out), '--threads', '3',
            '--reuse-pair', str(parent/'v1'/name), str(parent/'v1/ktx'/name)], check=True)
    print('PACKED_VEHICLE', piece, tier, flush=True)

if __name__ == '__main__':
    pieces = [p for p in VERSIONS if p.split('_')[0] in ('horse', 'chariot', 'cannon')]
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(compress, [(p,t) for p in pieces for t in ('desktop','mobile','distant')]))
