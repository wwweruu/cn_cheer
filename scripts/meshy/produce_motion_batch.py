"""Resume reviewed humanoid inputs or their clips under the shared credit guard."""
import argparse
import json
import sys
from motion_assets import motion_job, HUMANS, CLIPS
from pipeline import ROOT, Client, Pipeline, PipelineError, read_key, workspace_lock

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('rigs','clips'));parser.add_argument('--pieces',required=True)
    args=parser.parse_args();pieces=args.pieces.split(',')
    if not pieces or set(pieces)-HUMANS:raise PipelineError('Unknown humanoid selection')
    with workspace_lock(ROOT/'.meshy/live'):
        pipe=Pipeline(Client(read_key(),timeout=120),ROOT/'.meshy/live',ROOT/'assets/generated/meshy')
        jobs=[]
        for piece in pieces:
            if args.phase=='rigs':
                version=2 if piece=='soldier_red' else 1
                folder=ROOT/'assets/generated/meshy'/piece/f'rig-input/v{version}'
                info=json.loads((folder/'input.json').read_text(encoding='utf8'))
                jobs.append(motion_job(piece,'rig',model=str(folder/'model.glb'),height=info['height_meters']))
            else:
                rig=pipe.ledger['jobs'].get(f'{piece}/motion/rig/v1')
                if not rig or rig['state']!='SUCCEEDED':raise PipelineError(f'{piece}: rig not successful')
                for clip in CLIPS:
                    # Commanding figures use an open-arm strike; armed foot soldiers slash with the right hand.
                    action=214 if clip=='attack' and not piece.startswith('soldier') else CLIPS[clip]
                    jobs.append(motion_job(piece,clip,rig_task_id=rig['task_id'],action_id=action))
        print('Reviewed batch cost if new:',sum(j['estimate'] for j in jobs if j['key'] not in pipe.ledger['jobs']),flush=True)
        pipe.run_batch(jobs,max_active=3)

if __name__=='__main__':
    try:main()
    except (PipelineError,OSError,ValueError) as e:
        print(f'Stopped: {e}',file=sys.stderr);sys.exit(1)
