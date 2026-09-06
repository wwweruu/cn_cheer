# -*- coding: utf-8 -*-
"""Asset integrity audit 2026-09-06: manifests vs disk vs GLB headers."""
import json, hashlib, struct, os
from pathlib import Path

ROOT = Path(r"D:\个人资料\cn_chess")
ASSETS = ROOT / "public" / "assets"
REPORT = ROOT / "docs" / "asset-reports" / "integrity-audit-2026-09-06.md"

TEX_EXT = {".webp", ".png", ".jpg", ".jpeg", ".ktx", ".ktx2", ".hdr", ".exr"}

def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def glb_header(p):
    """Return (ok, detail)."""
    try:
        with open(p, "rb") as f:
            head = f.read(12)
    except OSError as e:
        return False, f"read error: {e}"
    if len(head) < 12:
        return False, f"file too small for GLB header ({len(head)} bytes)"
    magic, version, length = struct.unpack("<4sII", head)
    actual = p.stat().st_size
    if magic != b"glTF":
        return False, f"bad magic {magic!r}"
    if version != 2:
        return False, f"version={version} (expected 2)"
    if length != actual:
        return False, f"header length={length} != actual size={actual}"
    return True, "ok"

def main():
    manifests = {}
    for name in ["production-manifest.json", "motion-manifest.json"]:
        with open(ASSETS / name, "r", encoding="utf-8") as f:
            manifests[name] = json.load(f)

    results = []  # per manifest entry
    listed = {}   # abs path (lowercased, normalized) -> manifest name
    for mname, data in manifests.items():
        for e in data.get("files", []):
            rel = e["path"].lstrip("/")          # e.g. assets/models/...
            fs_path = ROOT / "public" / Path(rel.replace("\\", "/"))
            listed[str(fs_path).lower()] = mname
            rec = {"manifest": mname, "path": e["path"],
                   "m_bytes": e.get("bytes"), "m_sha": e.get("sha256"),
                   "exists": False, "size_ok": None, "sha_ok": None,
                   "actual_bytes": None, "actual_sha": None,
                   "glb": None, "issues": []}
            if not fs_path.is_file():
                rec["issues"].append("MISSING: file not found")
                results.append(rec)
                continue
            rec["exists"] = True
            actual = fs_path.stat().st_size
            rec["actual_bytes"] = actual
            if rec["m_bytes"] is not None:
                rec["size_ok"] = (actual == rec["m_bytes"])
                if not rec["size_ok"]:
                    rec["issues"].append(f"SIZE mismatch: manifest={rec['m_bytes']} actual={actual}")
            sha = sha256_of(fs_path)
            rec["actual_sha"] = sha
            if rec["m_sha"] is not None:
                rec["sha_ok"] = (sha.lower() == rec["m_sha"].lower())
                if not rec["sha_ok"]:
                    rec["issues"].append(f"SHA256 mismatch: manifest={rec['m_sha']} actual={sha}")
            if fs_path.suffix.lower() == ".glb":
                ok, detail = glb_header(fs_path)
                rec["glb"] = detail
                if not ok:
                    rec["issues"].append(f"GLB header: {detail}")
            results.append(rec)

    # reverse check: files on disk under public/assets not in any manifest
    orphans = []
    for p in sorted(ASSETS.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext != ".glb" and ext not in TEX_EXT:
            continue
        if str(p).lower() not in listed:
            orphans.append(str(p.relative_to(ROOT)))

    # GLB header check for orphaned GLBs too
    orphan_glb_bad = []
    for rel in orphans:
        p = ROOT / rel
        if p.suffix.lower() == ".glb":
            ok, detail = glb_header(p)
            if not ok:
                orphan_glb_bad.append((rel, detail))

    # stats
    total = len(results)
    ok_all = [r for r in results if r["exists"] and not r["issues"]]
    missing = [r for r in results if not r["exists"]]
    size_bad = [r for r in results if r["exists"] and r["size_ok"] is False]
    sha_bad = [r for r in results if r["exists"] and r["sha_ok"] is False]
    glb_checked = [r for r in results if r["glb"] is not None]
    glb_bad = [r for r in results if r["glb"] not in (None, "ok")]
    glb_total = len(glb_checked) + sum(1 for rel in orphans if rel.lower().endswith(".glb"))

    lines = []
    A = lines.append
    A("# 资产完整性校验报告 — 2026-09-06\n")
    A("## 清单结构说明\n")
    A("两份清单均为 JSON，顶层结构：\n")
    A("- `production-manifest.json`：`files`（128 条）+ `missing`（数组，当前为空）。"
      "每条 `files` 记录含 `source`（生成来源，本地反斜杠路径）、`path`（运行时 URL 路径，"
      "形如 `/assets/models/...`，对应磁盘 `public/assets/...`）、`bytes`（体积）、`sha256`（小写十六进制）。")
    A("- `motion-manifest.json`：`files`（84 条，字段同前）+ `versions`（按棋子名记录版本信息）。无 `missing` 字段。\n")
    A("## 校验方法\n")
    A("对每条清单记录依次检查：文件存在性 → 实际字节数 vs `bytes` → 重新计算 SHA-256 vs `sha256`；"
      "所有 `.glb` 再校验二进制头（magic 应为 `glTF`、version 应为 2、header 中的 length 应等于文件实际大小）。"
      "反向扫描 `public/assets/` 下的 `.glb` 与纹理文件（webp/png/jpg/jpeg/ktx/ktx2/hdr/exr），"
      "找出未列入任何清单的孤立文件。\n")
    A("## 结果统计\n")
    A("| 指标 | 数量 |")
    A("|---|---|")
    A(f"| 清单条目总数 | {total} |")
    A(f"| 全部通过（存在+大小+哈希+GLB头） | {len(ok_all)} |")
    A(f"| 缺失文件 | {len(missing)} |")
    A(f"| 大小不一致 | {len(size_bad)} |")
    A(f"| SHA-256 不一致 | {len(sha_bad)} |")
    A(f"| GLB 头异常（清单内） | {len(glb_bad)} |")
    A(f"| GLB 头检查总数（含孤立 GLB） | {glb_total} |")
    A(f"| 孤立文件（在盘上、不在清单） | {len(orphans)} |")
    A("")

    def fail_section(title, items, fmt):
        A(f"## {title}（{len(items)} 项）\n")
        if not items:
            A("无。\n")
        else:
            for it in items:
                A(fmt(it))
            A("")

    fail_section("缺失文件", missing, lambda r: f"- `{r['path']}`（{r['manifest']}）")
    fail_section("大小不一致", size_bad,
                 lambda r: f"- `{r['path']}`：清单 {r['m_bytes']} 字节，实际 {r['actual_bytes']} 字节")
    fail_section("SHA-256 不一致", sha_bad,
                 lambda r: f"- `{r['path']}`：\n  - 清单 `{r['m_sha']}`\n  - 实际 `{r['actual_sha']}`")
    fail_section("GLB 头异常", glb_bad, lambda r: f"- `{r['path']}`：{r['glb']}")

    A(f"## 孤立文件（在盘上但不在任何清单，共 {len(orphans)} 个）\n")
    if not orphans:
        A("无。\n")
    else:
        for rel in orphans:
            sz = (ROOT / rel).stat().st_size
            A(f"- `{rel}`（{sz} 字节）")
        A("")
    A(f"## 孤立 GLB 头异常（{len(orphan_glb_bad)} 项）\n")
    if not orphan_glb_bad:
        A("无。\n")
    else:
        for rel, d in orphan_glb_bad:
            A(f"- `{rel}`：{d}")
        A("")

    # history comparison
    try:
        with open(ROOT / "docs/asset-reports/validation.json", "r", encoding="utf-8") as f:
            hist = json.load(f)
        A("## 与历史 validation.json 的对照\n")
        A("`docs/asset-reports/validation.json` 是 2026 年早些时候的构建/测试证据，并非资产哈希清单，"
          "记录的是：前端单测 %d、API 离线测试 %d、lint %s、生产构建 %s、E2E 通过 %d / 跳过 %d、"
          "motion 变体 %d、clip×tier 组合 %d、每组合采样 %d、动画最大固定位移误差 %.3e、"
          "物理机移动端测试 %s、native 2k 天空盒 %s。"
          "它与本次校验没有可直接比对的哈希/体积字段；本次完整性校验是该记录的补充"
          "（其只证明当时构建与测试通过，不证明盘上资产与清单逐字节一致）。" %
          (hist["frontend_unit_tests"], hist["api_offline_tests"], hist["lint"],
           hist["production_build"], hist["e2e"]["passed"], hist["e2e"]["skipped"],
           hist["motion_variants"], hist["clip_tier_combinations"],
           hist["samples_per_combination"], hist["motion_max_fixed_base_displacement"],
           hist["physical_mobile_tested"], hist["native_sky_2k"]))
        A("")
    except Exception as e:
        A(f"## 与历史 validation.json 的对照\n读取失败：{e}\n")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "total": total, "passed": len(ok_all), "missing": [r["path"] for r in missing],
        "size_bad": [r["path"] for r in size_bad], "sha_bad": [r["path"] for r in sha_bad],
        "glb_bad": [(r["path"], r["glb"]) for r in glb_bad],
        "orphans": orphans, "orphan_glb_bad": orphan_glb_bad,
        "glb_total": glb_total, "report": str(REPORT),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
