# -*- coding: utf-8 -*-
"""AI 重生成：人脸三视图 + 无脸身体三视图（参考图驱动，可断点续跑）
用法: python _regen_faces.py [batch_size]
"""
import subprocess, sys, json, re
from pathlib import Path

PLUGIN = Path(r"C:/Users/guyu/AppData/Roaming/kimi-desktop/daimon-share/daimon/runtime/kimi-code/home/plugins/managed/image_generation")
TOOL = PLUGIN / "scripts" / "image_generation_tool.py"
ROOT = Path(r"C:\Users\guyu\cn_cheer\象棋3D参考图")
MERGED = ROOT / "三视图合并"
FACE_OUT = ROOT / "人脸三视图_AI"
BODY_OUT = ROOT / "无脸身体三视图_AI"
FACE_OUT.mkdir(exist_ok=True)
BODY_OUT.mkdir(exist_ok=True)
STATE = ROOT / "_face_state.json"

PIECES = ["帅-红方", "将-黑方", "仕-红方", "士-黑方", "相-红方", "象-黑方",
          "马-红方", "马-黑方", "车-红方", "车-黑方", "炮-红方", "炮-黑方",
          "兵-红方", "卒-黑方"]

FACE_PROMPT = (
    "3D建模工程参考图，正交视图无透视，横版。以参考图中的人物为准，生成其头部特写三视图并排："
    "左侧正面、中间正侧面90°、右侧正后方180°，三格等分画面。"
    "保留原有头盔/冠饰/发型/须髯与阵营配色，面部五官细节清晰写实，"
    "均匀无影棚光，纯灰背景，头部撑满各自画格、完整无裁切，无动作无风无模糊。"
)
BODY_PROMPT = (
    "将参考图中所有人物的面部替换为无五官的光滑空白面部（均匀肤色的空白面壳，无眼、无鼻、无口、无眉，完全放空留白），"
    "身体、盔甲、武器、马匹、战象、战车、机械、底座与刻字等其余一切保持与参考图完全一致，"
    "正交视图无透视，均匀无影棚光，纯灰背景，主体完整无裁切。"
)

def run_tool(args):
    r = subprocess.run([sys.executable, str(TOOL)] + args, cwd=str(PLUGIN),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=280)
    return (r.stdout or "") + (r.stderr or "")

def load_state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}

def save_state(st):
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")

def find_out(folder, stem):
    for ext in (".png", ".jpg", ".jpeg"):
        p = folder / (stem + ext)
        if p.exists() and p.stat().st_size > 10000:
            return str(p)
    return None

def main():
    batch = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    state = load_state()
    done = 0
    for name in PIECES:
        if done >= batch:
            break
        ref_local = MERGED / f"{name}-三视图.png"
        url_key = f"{name}__url"
        if url_key not in state:
            print(f"[UPLOAD] {name}", flush=True)
            up = run_tool(["image-to-url", "--image-path", str(ref_local)])
            m = re.search(r"https?://\S+", up)
            if not m:
                print(f"[FAIL-UPLOAD] {name}: {up[-400:]}", flush=True)
                continue
            state[url_key] = m.group(0)
            save_state(state)
        url = state[url_key]
        for kind, outdir, prompt in (
            ("face", FACE_OUT, FACE_PROMPT),
            ("body", BODY_OUT, BODY_PROMPT),
        ):
            tkey = f"{name}__{kind}"
            if tkey in state or find_out(outdir, name):
                if tkey not in state:
                    state[tkey] = find_out(outdir, name)
                    save_state(state)
                continue
            if done >= batch:
                break
            out = outdir / f"{name}.png"
            print(f"[GEN] {tkey} ...", flush=True)
            try:
                log = run_tool(["generate", "--description", prompt, "--ratio", "16:9",
                                "--resolution", "2K", "--background", "opaque",
                                "--reference-image", url, "--output", str(out)])
            except subprocess.TimeoutExpired:
                print(f"[TIMEOUT] {tkey}", flush=True)
                continue
            saved = find_out(outdir, name)
            if saved:
                state[tkey] = saved
                save_state(state)
                done += 1
                print(f"[OK] {tkey}", flush=True)
            else:
                print(f"[FAIL] {tkey}: {log[-600:]}", flush=True)
    remaining = [k for n in PIECES for k in (f"{n}__face", f"{n}__body")
                 if k not in load_state()]
    print(f"=== done_this_run={done}, remaining={len(remaining)} ===", flush=True)
    for r in remaining:
        print("  - " + r, flush=True)

if __name__ == "__main__":
    main()
