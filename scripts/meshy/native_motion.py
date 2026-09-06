"""Generate and retarget Meshy motion using the existing durable credit ledger."""
import argparse
import hashlib
import json
import math
import re
import sys

from pipeline import ROOT, RIGGING, ANIMATION, TEXT_MOTION, Client, Pipeline, PipelineError, read_key, workspace_lock
from scene_assets import local_input


def native_job(spec, ledger, root=ROOT):
    piece, role, operation = spec['piece'], spec['role'], spec['operation']
    version = spec.get('version', 1)
    if any(not isinstance(v, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,60}', v) for v in (piece, role, operation)):
        raise PipelineError('Invalid native motion asset name')
    if isinstance(version, bool) or version not in (1, 2, 3):
        raise PipelineError('Native API variants must be 1..3')
    model = None
    if operation == 'generate':
        prompt, duration, mode = spec['prompt'], spec['duration'], spec.get('mode', 'prime')
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 400:
            raise PipelineError('Motion prompt must contain 1..400 characters')
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 2 <= duration <= 10 or duration * 2 != round(duration * 2):
            raise PipelineError('Duration must be 2..10 seconds in 0.5-second steps')
        if mode not in ('prime', 'swift'):
            raise PipelineError('Unknown motion generation mode')
        endpoint, cost = TEXT_MOTION, 10 if mode == 'prime' else 3
        params = {'prompt': prompt, 'duration': duration, 'mode': mode}
    elif operation == 'rig':
        height, skeleton = spec['height'], spec.get('skeleton', 'biped')
        if isinstance(height, bool) or not isinstance(height, (int, float)) or not math.isfinite(height) or height <= 0:
            raise PipelineError('Invalid character height')
        if skeleton not in ('biped', 'quadruped'):
            raise PipelineError('Unsupported skeleton type')
        model = local_input(spec['model'], root, model=True)
        endpoint, cost = RIGGING, 5
        params = {'height_meters': height, 'animation_type': skeleton}
    else:
        rig = ledger['jobs'].get(spec['rig_key'])
        if not rig or rig.get('endpoint') != RIGGING or rig['state'] != 'SUCCEEDED' or rig['piece'] != piece:
            raise PipelineError('A successful matching piece rig is required')
        generated = spec.get('motion_key')
        preset = spec.get('action_id')
        if (generated is None) == (preset is None):
            raise PipelineError('Specify exactly one generated motion or preset')
        params = {'rig_task_id': rig['task_id']}
        if generated is not None:
            motion = ledger['jobs'].get(generated)
            if not motion or motion.get('endpoint') != TEXT_MOTION or motion['state'] != 'SUCCEEDED':
                raise PipelineError('A successful generated motion is required')
            if rig['params'].get('animation_type', 'biped') != 'biped':
                raise PipelineError('Generated motion retargeting requires biped rig')
            params['motion_task_id'] = motion['task_id']
        else:
            if isinstance(preset, bool) or not isinstance(preset, int) or not 0 <= preset <= 32767:
                raise PipelineError('Invalid preset action')
            params['action_id'] = preset
        endpoint, cost = ANIMATION, 3
    inputs = {'endpoint': endpoint, 'params': params, 'images': [], 'model': model}
    fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    job = {'key': f'{piece}/native/{role}/{operation}/v{version}', 'piece': piece, 'variant': version,
           'endpoint': endpoint, 'params': params, 'images': [], 'estimate': cost,
           'fingerprint': fingerprint, 'asset_kind': operation, 'role': role}
    if model:
        job['model'] = model
    return job


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'run'))
    parser.add_argument('--spec', required=True)
    args = parser.parse_args()
    specs = json.loads((ROOT / args.spec).read_text(encoding='utf-8'))['jobs']
    with workspace_lock(ROOT / '.meshy/live'):
        ledger = json.loads((ROOT / '.meshy/live/ledger.json').read_text(encoding='utf-8'))
        jobs = [native_job(s, ledger) for s in specs]
        if args.command == 'plan':
            print(json.dumps({'cost_if_new': sum(j['estimate'] for j in jobs if j['key'] not in ledger['jobs']), 'jobs': jobs}, ensure_ascii=False, indent=2))
            return
        pipeline = Pipeline(Client(read_key(), timeout=120), ROOT / '.meshy/live', ROOT / 'assets/generated/meshy')
        pipeline.run_batch(jobs, max_active=3)


if __name__ == '__main__':
    try:
        main()
    except (PipelineError, OSError, ValueError) as error:
        print(f'Stopped: {error}', file=sys.stderr)
        sys.exit(1)
