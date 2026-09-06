"""Publish only review candidates; the game's production manifest is unchanged."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[1]
BASELINE = {'soldier_red':13,'soldier_black':16,'general_black':8,'advisor_red':7,
            'horse_red':10,'horse_black':6,'cannon_red':11,'cannon_black':9,
            'elephant_red':3,'elephant_black':3}
VERSIONS = {'soldier_red':14,'soldier_black':19,'general_black':20,'advisor_red':8,
            'horse_red':12,'horse_black':8,'cannon_red':13,'cannon_black':11,
            'elephant_red':8,'elephant_black':8}
NOTES = {
    'soldier_red':'保留 API 生成步行；重建脚踝连续权重，匹配完整步行周期，修正首尾闭合和脚底高度。剑盾保持刚性跟随。',
    'soldier_black':'去除剑盾干扰后重新进行 API 绑定和动作生成，再装回原始装备。脚踝、衣摆与持盾接触仍需复核。',
    'general_black':'去除旗枪干扰后重新进行 API 绑定，生成警戒和步行动作。原模型手掌与旗枪的接触仍不准确，尚未通过质量验收。',
    'advisor_red':'保留 API 观察待机、原始长袍与固定站姿；闭合循环首尾，避免重复播放时突跳。衣袖与羽扇的细节仍需复核。',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--versions', help='Optional JSON mapping of piece to reviewed local version')
    args = parser.parse_args()
    versions = VERSIONS | (json.loads((ROOT/args.versions).read_text(encoding='utf-8')) if args.versions else {})
    rows = []
    for piece, version in versions.items():
        parent = ROOT/'assets/generated/meshy'/piece/f'motion/runtime/v{version}'
        source = parent/f'{piece}_mobile.glb'
        report = json.loads((parent/'runtime.json').read_text(encoding='utf-8'))
        raw = source.read_bytes(); size = struct.unpack_from('<I', raw, 12)[0]; doc = json.loads(raw[20:20+size])
        assert len(doc['skins']) == 1 and len(doc['animations']) == 6
        assert report['sources_unchanged']
        assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest for path, digest in report['sources'].items())
        clips = [name for name, info in report.get('clip_sources', {}).items() if info['text_to_motion']]
        if piece.startswith(('horse','elephant','cannon')):
            clips = ['idle']
        review_clips = report.get('review_clips', clips)
        note = NOTES.get(piece)
        if piece.startswith('horse'):
            note = 'API 生成骑手观察和调缰动作，坐姿已作校准。马身沿用现有局部关节动作，尚无成功的四足 API 绑定结果。持枪接触仍需复核。'
        elif piece.startswith('elephant'):
            note = 'API 生成象背弓手的抬臂、瞄准动作。象身仍是旧版局部动作；四足绑定被服务端以姿态估计失败拒绝，真实步态尚未解决。弓与手的接触仍需复核。'
        elif piece.startswith('cannon'):
            note = '修复炮手骨骼朝向、低处部件的错误手部权重，并保留 API 头部、手臂动作。炮架和发射机构沿用既有机械动作；近景手部仍需精修。'
        if piece == 'soldier_black' and version >= 18:
            note = '保留 API 动作；从原高模恢复被上传裁切移除的鞋面，重建小腿与脚踝连续权重，收敛持剑持盾动作。步态与衣摆仍在复核。'
        if piece == 'general_black' and version >= 9:
            note = '保留 API 步行动作；修正小腿权重，恢复持械时的上身姿态。原高模手掌尚未握紧枪杆，手指接触仍待修整。'
        if report.get('grip_refinement'):
            note = '以原始手部表面拟合握持姿态，枪杆独立保持刚性，手臂跟随握持点。另修正披风与靴子的权重和循环首尾；近景手指与披风边缘仍需精修。'
        if report.get('contact_refinement'):
            if piece.startswith('horse'):
                note = '修复骑手骨骼朝向，并用双关节约束稳定持枪手与左手落点；保留 API 头部与上身表演。马身仍沿用本地关节动作。'
            if piece.startswith('elephant'):
                note = '象身改为本地四足骨架和分阶段落脚轨迹，新增行进预览；背上弓手保留 API 动作。四足步态是本地制作，尚需侧面和循环自然度复核。'
        assert clips, piece
        destination = ROOT/'public/assets/models/native-motion'/piece/f'v{version}.webp.glb'
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            assert destination.read_bytes() == raw, 'Review candidate versions are immutable'
        else:
            shutil.copy2(source, destination)
        count = sum(doc['accessors'][primitive['indices']]['count']//3 for mesh in doc['meshes'] for primitive in mesh['primitives'])
        manifest = {'variants': {'mobile': {'file':'/'+str(destination.relative_to(ROOT/'public')).replace('\\','/'), 'bytes':len(raw),'triangles':count}},
            'generated_clips': clips, 'review_clips': review_clips, 'note': note, 'source_version': version, 'production_replaced':False,
            'sha256':hashlib.sha256(raw).hexdigest()}
        review = ROOT/'public/assets/review/native-motion'/piece
        review.mkdir(parents=True, exist_ok=True)
        (review/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        # A stable comparison target for this refinement round. Existing source
        # GLBs remain immutable, including their original API/local provenance.
        old_version = BASELINE[piece]
        old_path = ROOT/'public/assets/models/native-motion'/piece/f'v{old_version}.webp.glb'
        old_raw = old_path.read_bytes()
        old_report = json.loads((ROOT/'assets/generated/meshy'/piece/f'motion/runtime/v{old_version}/runtime.json').read_text(encoding='utf-8'))
        old_clips = [n for n,i in old_report.get('clip_sources',{}).items() if i['text_to_motion']]
        if piece.startswith(('horse','elephant','cannon')): old_clips = ['idle']
        old_manifest = {'variants': {'mobile': {'file':'/'+str(old_path.relative_to(ROOT/'public')).replace('\\','/'),'bytes':len(old_raw),'triangles':old_report['files']['mobile']['triangles']}},'generated_clips':old_clips,'review_clips':old_clips,'note':'上一轮样板，用于对照本轮骨骼、脚踝与接触修整。','source_version':old_version,'production_replaced':False,'sha256':hashlib.sha256(old_raw).hexdigest()}
        (review/'before.json').write_text(json.dumps(old_manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        rows.append({'piece':piece,**manifest,'source':str(source.relative_to(ROOT)).replace('\\','/')})
        print('NATIVE_REVIEW_STAGED',piece,version,review_clips,flush=True)
    output = ROOT/'docs/asset-reports/native-motion'
    output.mkdir(parents=True,exist_ok=True)
    (output/'staging.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__':main()
