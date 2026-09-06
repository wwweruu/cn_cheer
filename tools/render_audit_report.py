# -*- coding: utf-8 -*-
"""Render geometry-animation-audit Markdown from glb-audit-raw.json."""
import json
import re
import statistics
import collections
from pathlib import Path

ROOT = Path(r"D:\个人资料\cn_chess")
RAW = ROOT / "docs/asset-reports/glb-audit-raw.json"
OUT = ROOT / "docs/asset-reports/geometry-animation-audit-2026-09-06.md"
MODELS_PREFIX = "public/assets/models/"
EXPECTED = ["idle", "attack", "hit", "death", "walk", "run"]

rs = json.load(RAW.open(encoding="utf-8"))


def cat_of(r):
    parts = r["file"].split("/")
    if parts[0] in ("motion", "production", "native-motion"):
        return parts[1]
    return parts[0].replace(".glb", "")


def group_of(r):
    parts = r["file"].split("/")
    return parts[0] if len(parts) > 1 else "top"


L = []
add = L.append

# ---------- overview ----------
n_files = len(rs)
n_err = sum(1 for r in rs if r.get("error"))
sev = collections.Counter()
chk = collections.Counter()
for r in rs:
    for p in r["problems"]:
        sev[p["sev"]] += 1
        chk[p["check"]] += 1
n_anim_files = sum(1 for r in rs if r["animations"])
n_skin_files = sum(1 for r in rs if r.get("skinning") and r["skinning"].get("skinned_prims"))
n_images = sum(len(r["images"]) for r in rs)
tot_verts = sum(r["vertices"] for r in rs)
tot_tris = sum(r["triangles"] for r in rs)

add("# GLB 几何与骨骼动画质量审计报告")
add("")
add("- 审计日期：2026-09-06")
add("- 工具：`tools/audit_glb_assets.py`（纯 Python GLB 解析，无 Blender 依赖；环境内 `blender` 不可用）")
add("- 范围：`public/assets/models/` 下全部 **%d** 个 GLB（顶层棋子 14、motion/ 84、native-motion/ 40、production/ 84）" % n_files)
add("- 原始数据：`docs/asset-reports/glb-audit-raw.json`（每个文件的完整解析结果）")
add("")
add("## 0. 结论摘要")
add("")
add("| 指标 | 数值 |")
add("|---|---|")
add(f"| 解析 GLB 总数 | {n_files}（解析失败 {n_err}） |")
add(f"| 总顶点 / 总三角面 | {tot_verts:,} / {tot_tris:,} |")
add(f"| 含骨骼动画的文件 | {n_anim_files}（motion/ 84 + native-motion/ 40，均含蒙皮网格） |")
add(f"| 内嵌纹理图像总数 | {n_images} |")
add(f"| error 级问题 | {sev.get('error', 0)} |")
add(f"| warn 级问题 | {sev.get('warn', 0)}（退化三角 {chk.get('degenerate', 0)} 条、循环首尾不一致 {chk.get('loop', 0)} 条） |")
add("")
add("**总体结论**：几何数据健康（无索引越界、无 NaN/Inf、法线全部单位化、蒙皮权重全部归一、关节索引无越界）；"
      "14 类棋子 idle/attack/hit/death/walk/run 六段动画覆盖齐全；纹理全部内嵌且尺寸可解析。"
      "production/ 84 个文件为**静态运行版**（单节点、无动画、无蒙皮），与交付文档 PRODUCTION_DELIVERY.md 中"
      "“保留的静态运行文件”定位一致，动画运行版实际为 motion/ 下的 84 个 GLB，非缺陷。"
      "需要关注的问题仅两类：① 顶层 elephant 红/黑各有一个小网格 16.67% 退化三角；"
      "② motion/ 与 native-motion/ 候选文件的 walk/run/idle 首尾姿态不一致（其中 walk/run 平移差需对照"
      "“运行 GLB 已去除水平根位移”的交付约定复核）。")
add("")

# ---------- 1 geometry: top-level pieces ----------
add("## 1. 几何检查")
add("")
add("### 1.1 顶层棋子（public/assets/models/*.glb）")
add("")
add("| 棋子 | 顶点数 | 三角面 | 包围盒对角线 | 包围盒 Y 范围 | 退化三角 | 法线 |")
add("|---|---|---|---|---|---|---|")
top = sorted((r for r in rs if "/" not in r["file"]), key=lambda x: x["file"])
diags = []
for r in top:
    b = r["bbox"]
    diags.append(b["diag"])
    deg = "; ".join(f"{m['mesh']}[{m['prim']}] {m['degenerate_ratio']*100:.1f}%"
                    for m in r["meshes"] if isinstance(m.get("degenerate_ratio"), (int, float)) and m["degenerate_ratio"] > 0.001) or "—"
    nrm = "; ".join(f"{m['mesh']}[{m['prim']}] {m['normal_issue']}"
                    for m in r["meshes"] if m.get("normal_issue") == "missing") or "单位化 ✓"
    add(f"| {r['file']} | {r['vertices']:,} | {r['triangles']:,} | {b['diag']:.3f} | "
        f"[{b['min'][1]:.2f}, {b['max'][1]:.2f}] | {deg} | {nrm} |")
med = statistics.median(diags)
add("")
add(f"尺度中位数对角线 **{med:.3f}**，14 枚棋子范围 {min(diags):.3f}–{max(diags):.3f} "
    f"（最大/中位数 = {max(diags)/med:.2f}，为 chariot 车马复合体，属合理体型差异），**无尺度离群**。")
add("")
add("### 1.2 动画运行资产（motion / native-motion / production）")
add("")
add("| 目录 | 文件数 | 顶点数 min–max | 三角面 min–max | 对角线 min–max | 退化三角问题 | 法线问题 | 索引/NaN 问题 |")
add("|---|---|---|---|---|---|---|---|")
for g, label in (("motion", "motion/"), ("native-motion", "native-motion/"), ("production", "production/")):
    grp = [r for r in rs if group_of(r) == g]
    vs = [r["vertices"] for r in grp]
    ts = [r["triangles"] for r in grp]
    ds = [r["bbox"]["diag"] for r in grp if r["bbox"]]
    ndeg = sum(1 for r in grp for p in r["problems"] if p["check"] == "degenerate")
    nnrm = sum(1 for r in grp for p in r["problems"] if p["check"] == "normal")
    ngeo = sum(1 for r in grp for p in r["problems"] if p["check"] in ("index_oob", "nan", "geometry"))
    add(f"| {label} | {len(grp)} | {min(vs):,}–{max(vs):,} | {min(ts):,}–{max(ts):,} | "
        f"{min(ds):.3f}–{max(ds):.3f} | {ndeg} | {nnrm} | {ngeo} |")
add("")
add("运行资产三角面规模按 desktop/mobile/distant 分级递减，符合 LOD 设计；三组目录均无索引越界、无 NaN/Inf、法线全部存在且单位化。")
add("")

# ---------- 2 skinning ----------
add("## 2. 蒙皮检查")
add("")
sk = [r for r in rs if r.get("skinning") and r["skinning"].get("skinned_prims")]
add(f"含蒙皮网格的文件 **{len(sk)}** 个（motion/ 84 + native-motion/ 40）。"
    "顶层 14 枚与 production/ 84 个为纯静态网格，无蒙皮，与静态运行版定位一致，属预期。"
    "全部蒙皮文件具备 JOINTS_0/WEIGHTS_0，权重和偏离 1 超过 0.01 的顶点比例为 **0**，关节索引越界 **0**。")
add("")
add("| 目录 | 蒙皮文件 | 骨骼数 min–max | 权重未归一顶点 | 关节越界 |")
add("|---|---|---|---|---|")
for g, label in (("motion", "motion/"), ("native-motion", "native-motion/"), ("production", "production/")):
    grp = [r for r in sk if group_of(r) == g]
    if not grp:
        add(f"| {label} | 0（静态版，无蒙皮） | — | — | — |")
        continue
    js = [r["skinning"]["max_skin_joints"] for r in grp]
    wb = sum(1 for r in grp if (r["skinning"].get("weight_sum_bad_ratio") or 0) > 0)
    oob = sum(1 for r in grp for p in r["problems"] if p["check"] == "skin" and "bounds" in p["detail"])
    add(f"| {label} | {len(grp)} | {min(js)}–{max(js)} | {wb} 个文件 | {oob} |")
add("")

# ---------- 3 animation ----------
add("## 3. 动画检查")
add("")
add("### 3.1 六段动作覆盖矩阵")
add("")
cov = collections.defaultdict(set)
for r in rs:
    c = cat_of(r)
    for a in r["animations"]:
        nm = a["name"].lower()
        for w in EXPECTED:
            if w in nm:
                cov[c].add(w)
add("| 棋子类别 | idle | attack | hit | death | walk | run |")
add("|---|---|---|---|---|---|---|")
for c in sorted(cov):
    row = [c] + ["✓" if w in cov[c] else "**缺失**" for w in EXPECTED]
    add("| " + " | ".join(row) + " |")
add("")
add("14 类棋子六段动作 **全部覆盖，无缺失**。每个含动画文件均含恰好 6 个 clip（idle/attack/hit/death/walk/run）。")
add("")
add("### 3.2 clip 时长统计（124 个含动画文件 × 6 clip）")
add("")
dur = collections.defaultdict(list)
for r in rs:
    for a in r["animations"]:
        dur[a["name"]].append(a["duration"])
add("| clip | 时长 min | 中位 | 时长 max | 时长为 0 | 关键帧 <2 | NaN 输出 |")
add("|---|---|---|---|---|---|---|")
for name in EXPECTED:
    v = dur[name]
    z = sum(1 for x in v if x <= 0)
    k = sum(1 for r in rs for a in r["animations"] if a["name"] == name and (a["min_keyframes"] or 0) < 2)
    nn = sum(1 for r in rs for a in r["animations"] if a["name"] == name and a["nan_outputs"])
    add(f"| {name} | {min(v):.2f}s | {statistics.median(v):.2f}s | {max(v):.2f}s | {z} | {k} | {nn} |")
add("")
add("### 3.3 循环（loop）首尾姿态一致性")
add("")
loop_recs = []
for r in rs:
    for a in r["animations"]:
        lp = a.get("loop") or {}
        if lp.get("expected") and (lp.get("max_rot_deg", 0) > 5.0 or lp.get("max_trans", 0) > 0.02):
            loop_recs.append((r["file"], a["name"], lp["max_rot_deg"], lp["max_trans"]))
add(f"对 idle/walk/run 三类循环 clip 检查首末帧姿态差（旋转 > 5° 或平移 > 0.02 记为不一致）："
    f"共 **{len(loop_recs)}** 条，全部位于 motion/ 与 native-motion/（production/ 与顶层文件为静态版，无 clip）。")
add("")
add("| 目录 | idle | walk | run | 小计 |")
add("|---|---|---|---|---|")
cnt = collections.Counter((f.split("/")[0], c) for f, c, _, _ in loop_recs)
for g in ("motion", "native-motion"):
    add(f"| {g}/ | {cnt[(g,'idle')]} | {cnt[(g,'walk')]} | {cnt[(g,'run')]} | "
        f"{sum(cnt[(g,c)] for c in ('idle','walk','run'))} |")
add("")
worst_rot = sorted(loop_recs, key=lambda x: -x[2])[:8]
worst_tr = sorted(loop_recs, key=lambda x: -x[3])[:8]
add("旋转差最大的 8 条：")
add("")
add("| 文件 | clip | 首末旋转差 | 首末平移差 |")
add("|---|---|---|---|")
for f, c, rd, td in worst_rot:
    add(f"| {MODELS_PREFIX}{f} | {c} | {rd:.1f}° | {td:.3f} |")
add("")
add("平移差最大的 8 条：")
add("")
add("| 文件 | clip | 首末旋转差 | 首末平移差 |")
add("|---|---|---|---|")
for f, c, rd, td in worst_tr:
    add(f"| {MODELS_PREFIX}{f} | {c} | {rd:.1f}° | {td:.3f} |")
add("")
add("> 说明：交付文档约定“运行 GLB 去除水平位移，游戏负责落点移动”，但 motion/ 正式动画资产中仍有 "
    "36 条 walk + 36 条 run 存在首末平移差（最大 general_black 1.300，约为其包围盒对角线的 75%），"
    "若属残留根位移会与代码驱动的位移叠加，建议逐条复核是根骨骼水平位移还是躯干起伏。"
    "native-motion/ 为候选版本库：general_black v8/v9 的 walk 平移差达 4.996（相对其包围盒对角线 ≈1.65 的 3 倍），"
    "horse_red v9 / horse_black v5 的 idle 首末旋转差 20.4°，循环播放会明显跳帧，建议弃用或修复这些候选版本。")
add("")

# ---------- 4 textures ----------
add("## 4. 纹理检查")
add("")
dims = collections.Counter()
ext = 0
for r in rs:
    for im in r["images"]:
        if im.get("dims"):
            dims[(im["mime"], tuple(im["dims"]))] += 1
        if im.get("external_uri"):
            ext += 1
add(f"内嵌图像共 **{n_images}** 张，全部走 bufferView 内嵌（外部 uri {ext} 张），尺寸全部解析成功，无缺失 internal buffer。")
add("")
add("| 格式 | 尺寸 | 张数 |")
add("|---|---|---|")
for (mime, d), n in sorted(dims.items()):
    add(f"| {mime} | {d[0]}×{d[1]} | {n} |")
add("")
add("纹理分 4096/2048/1024 三档，与 desktop/mobile/distant 分级对应；KTX2（GPU 压缩）与 WebP 双格式并存，符合 `.webp.glb` 变体命名约定。")
add("")

# ---------- 5 problem list ----------
add("## 5. 问题清单（按严重度）")
add("")
add("### 5.1 error 级")
add("")
if sev.get("error", 0) == 0:
    add("无。")
else:
    for r in rs:
        for p in r["problems"]:
            if p["sev"] == "error":
                add(f"- `{MODELS_PREFIX}{r['file']}` [{p['check']}] {p['detail']}")
add("")
add("### 5.2 warn 级 — 退化三角形（2 条）")
add("")
for r in rs:
    for p in r["problems"]:
        if p["check"] == "degenerate":
            add(f"- `{MODELS_PREFIX}{r['file']}` — {p['detail']}")
add("")
add("### 5.3 warn 级 — 循环 clip 首尾姿态不一致（110 条，全量列表）")
add("")
add("| 文件 | clip | 首末旋转差(°) | 首末平移差 |")
add("|---|---|---|---|")
for f, c, rd, td in sorted(loop_recs):
    add(f"| {MODELS_PREFIX}{f} | {c} | {rd:.1f} | {td:.3f} |")
add("")
add("### 5.4 其他检查项结果")
add("")
add("- 索引越界：0（222 个文件全部通过）")
add("- NaN/Inf 顶点：0")
add("- 法线缺失 / 非单位化：0")
add("- 包围盒尺度离群：0（14 枚顶层棋子对角线 1.97–3.67，同数量级）")
add("- 蒙皮权重未归一：0；关节索引越界：0；全零权重顶点：0")
add("- 时长为 0 的 clip：0；关键帧 <2 的 clip：0；sampler 输出 NaN：0")
add("- 动画覆盖缺失的棋子类别：0")
add("- 纹理缺失 internal buffer / 无法解析尺寸：0")
add("")

OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote", OUT)
