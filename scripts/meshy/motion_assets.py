"""Explicit humanoid rig and preset clip jobs sharing the original credit ledger."""
import argparse
import hashlib
import json
import math
import re
import sys

from pipeline import (ROOT, RIGGING, ANIMATION, Client, Pipeline, PipelineError,
                      read_key, workspace_lock)
from scene_assets import local_input

HUMANS = {f"{kind}_{side}" for kind in ("general", "advisor", "soldier") for side in ("red", "black")}
CLIPS = {"idle": 0, "attack": 219, "hit": 178, "death": 189}


def motion_job(piece, operation, variant=1, *, model=None, height=1.7,
               rig_task_id=None, action_id=None, root=ROOT):
    if piece not in HUMANS or variant not in (1, 2, 3):
        raise PipelineError("Expected one of six humanoid pieces and variant 1..3")
    if operation == "rig":
        if not isinstance(height, (int, float)) or isinstance(height, bool) or not math.isfinite(height) or height <= 0:
            raise PipelineError("Height must be positive and finite")
        model_info = local_input(model, root, model=True)
        endpoint, cost, params = RIGGING, 5, {"height_meters": height}
    else:
        if operation not in CLIPS or not isinstance(rig_task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", rig_task_id):
            raise PipelineError("A known clip name and verified rig task ID are required")
        action = CLIPS[operation] if action_id is None else action_id
        if isinstance(action, bool) or not isinstance(action, int) or action < 0:
            raise PipelineError("Preset action ID must be a non-negative integer")
        model_info = None
        endpoint, cost, params = ANIMATION, 3, {"rig_task_id": rig_task_id, "action_id": action}
    inputs = {"endpoint": endpoint, "params": params, "images": [], "model": model_info}
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    job = {"key": f"{piece}/motion/{operation}/v{variant}", "piece": piece, "variant": variant,
           "endpoint": endpoint, "params": params, "images": [], "estimate": cost,
           "fingerprint": digest, "asset_kind": operation}
    if model_info:
        job["model"] = model_info
    return job


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "run"))
    parser.add_argument("--piece", required=True, choices=sorted(HUMANS))
    parser.add_argument("--operations", default="rig")
    parser.add_argument("--variant", type=int, default=1)
    parser.add_argument("--model")
    parser.add_argument("--height", type=float, default=1.7)
    parser.add_argument("--rig-task-id")
    parser.add_argument("--action-id", type=int)
    args = parser.parse_args()
    jobs = [motion_job(args.piece, operation, args.variant, model=args.model, height=args.height,
                       rig_task_id=args.rig_task_id, action_id=args.action_id) for operation in args.operations.split(",")]
    if args.command == "plan":
        print(json.dumps({"offline": True, "cost_if_new": sum(j["estimate"] for j in jobs), "jobs": jobs}, indent=2))
        return
    with workspace_lock(ROOT / ".meshy/live"):
        pipeline = Pipeline(Client(read_key(), timeout=120), ROOT / ".meshy/live", ROOT / "assets/generated/meshy")
        for job in jobs:
            if job["endpoint"] == ANIMATION:
                rigs = [r for r in pipeline.ledger["jobs"].values()
                        if r.get("task_id") == job["params"]["rig_task_id"] and r.get("endpoint") == RIGGING
                        and r["piece"] == job["piece"] and r["state"] == "SUCCEEDED"]
                if len(rigs) != 1:
                    raise PipelineError("Rig must be a successful, matching piece in this ledger")
        pipeline.run_batch(jobs, max_active=3)


if __name__ == "__main__":
    try:
        main()
    except (PipelineError, OSError, ValueError) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        sys.exit(1)
