"""Archive verified refinement versions without exposing API credentials or URLs."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from stage_native_motion_samples import VERSIONS, BASELINE

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'docs/asset-reports/native-motion/refinement'
browser=json.loads((out.parent/'browser/results.json').read_text(encoding='utf-8'))
staged=json.loads((out.parent/'staging.json').read_text(encoding='utf-8'))
assert len(browser)==len(staged)==10
assert all(not r['errors'] and r['comparisonSwitch'] and r['sourceVersion']==VERSIONS[r['piece']] for r in browser)
rows=[]
for entry in staged:
    piece=entry['piece'];version=VERSIONS[piece]
    folder=ROOT/'assets/generated/meshy'/piece/f'motion/runtime/v{version}'
    runtime=json.loads((folder/'runtime.json').read_text(encoding='utf-8'))
    audit=json.loads((out/f'{piece}-v{version}-contacts.json').read_text(encoding='utf-8'))
    assert len(audit['clips'])==len(entry['review_clips'])
    assert all(c['pedestal_drift_m']<1e-5 and c['loop_vertex_jump_m']<1e-5 for c in audit['clips'])
    assert all(f['min_surface_clearance_m']>-.001 for c in audit['clips'] for f in c['feet'].values())
    if piece.startswith('elephant'):
        assert all(f['support_error_max_m']<.003 for c in audit['clips'] for f in c['feet'].values())
    assert hashlib.sha256((folder/f'{piece}_mobile.glb').read_bytes()).hexdigest()==entry['sha256']
    assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in runtime['sources'].items())
    rows.append({'piece':piece,'previous_version':BASELINE[piece],'version':version,'sha256':entry['sha256'],
                 'review_clips':entry['review_clips'],'surface_audit':audit['clips'],'sources_unchanged':True})
ledger=json.loads((ROOT/'.meshy/live/ledger.json').read_text(encoding='utf-8'))
spend=sum(job.get('reported_credits',0) or 0 for job in ledger['jobs'].values())
assert spend==1395
result={'recorded_at':datetime.now(timezone.utc).isoformat(),'api_spend_this_refinement':0,'project_spend':spend,
        'project_limit':1800,'project_remaining':1800-spend,'production_replaced':False,'visual_acceptance':False,
        'technical_checks':{'browser_pieces':len(browser),'browser_clips':sum(len(r['clips']) for r in browser),'comparison_switches':10,
                            'console_errors':0,'loop_max_vertex_jump_m':max(c['loop_vertex_jump_m'] for r in rows for c in r['surface_audit'])},
        'known_issues':['Some garment and cape edges still show excess deformation at close range.',
                        'Finger shapes and some rider/tool contacts need art refinement.',
                        'Only the listed idle/walk clips were reviewed; other packaged clips are not approved.',
                        'Quadruped gait is locally authored; the earlier API quadruped rejections remain unresolved.'],
        'pieces':rows}
(out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('REFINEMENT_VERIFIED',result['technical_checks'],'api_spend',0,'remaining',1800-spend)
