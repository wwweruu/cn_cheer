"""Explicit scene jobs using the same paid ledger, transport and recovery as pieces."""
import hashlib
import json
from pathlib import Path
import re

from pipeline import (ROOT, PipelineError, SINGLE_IMAGE, RETEXTURE, TEXT_IMAGE,
                      EDIT_IMAGE, inspect_glb)


def local_input(value, root, *, model=False):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise PipelineError("Asset input must be an existing file inside this project")
    data = path.read_bytes()
    if len(data) > (256 if model else 20) * 1024 * 1024:
        raise PipelineError("Asset input exceeds local size limit")
    info = {"path": str(path.relative_to(root.resolve())), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}
    if model:
        inspect_glb(path)
    else:
        info["mime"] = "image/png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if data.startswith(b"\xff\xd8\xff") else None
        if not info["mime"]:
            raise PipelineError("Scene references must be JPEG or PNG")
    return info


def load_scene_jobs(manifest, selection="all", variant=1, root=ROOT):
    if variant not in (1, 2, 3):
        raise PipelineError("variant must be 1..3")
    path = (root / manifest).resolve()
    if not path.is_relative_to(root.resolve()):
        raise PipelineError("Manifest must be inside the project")
    entries = json.loads(path.read_text(encoding="utf-8"))["assets"]
    selected = {entry["id"] for entry in entries} if selection == "all" else set(selection.split(","))
    if not selected or selected - {entry["id"] for entry in entries}:
        raise PipelineError("Unknown scene asset selection")
    jobs = []
    for entry in entries:
        asset = entry["id"]
        if asset not in selected:
            continue
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,60}", asset):
            raise PipelineError("Invalid asset ID")
        images = [local_input(value, root) for value in entry.get("references", [])]
        kind, model = entry["kind"], None
        if kind == "image":
            if len(images) > 5:
                raise PipelineError("Image editing accepts up to five references")
            endpoint = EDIT_IMAGE if images else TEXT_IMAGE
            ratio = entry.get("aspect_ratio", "1:1")
            if ratio not in {"1:1", "16:9", "9:16", "4:3", "3:4"}:
                raise PipelineError("Unsupported image aspect ratio")
            params = {"ai_model": "nano-banana-pro", "prompt": entry["prompt"],
                      "aspect_ratio": ratio, "generate_multi_view": False,
                      "remove_background": bool(entry.get("remove_background", False))}
            cost = 9
        elif kind == "geometry":
            if len(images) != 1:
                raise PipelineError("Board Image-to-3D needs one approved reference")
            endpoint = SINGLE_IMAGE
            params = {"ai_model": "meshy-7", "ultra_mode": False,
                      "should_texture": True, "enable_pbr": True, "texture_resolution": "8k",
                      "should_remesh": False, "image_enhancement": False,
                      "remove_lighting": True, "auto_size": False,
                      "target_formats": ["glb"], "multi_view_thumbnails": True}
            cost = 35
        elif kind == "surface":
            if images:
                raise PipelineError("Surface profile uses a text style, no competing image style")
            endpoint = RETEXTURE
            model = local_input(entry["model"], root, model=True)
            params = {"ai_model": "meshy-7", "enable_original_uv": True,
                      "enable_pbr": True, "texture_resolution": "4k",
                      "text_style_prompt": entry["prompt"], "target_formats": ["glb"]}
            cost = 10
        else:
            raise PipelineError("Unknown scene operation")
        fingerprint = {"endpoint": endpoint, "params": params, "images": images, "model": model}
        digest = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        job = {"key": f"scene/{asset}/{kind}/v{variant}", "piece": asset, "variant": variant,
               "endpoint": endpoint, "fingerprint": digest, "params": params,
               "images": images, "estimate": cost, "asset_kind": kind}
        if model:
            job["model"] = model
        jobs.append(job)
    return jobs
