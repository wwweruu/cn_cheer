"""Usage: python scripts/meshy/cli.py --help (or npm run meshy -- --help)."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile

from pipeline import (BALANCE_FLOOR, BUDGET, Client, Pipeline, PipelineError,
                      ENDPOINT, SINGLE_IMAGE, RETEXTURE, PRICE_DATE, ROOT, atomic_json, load_jobs,
                      load_retexture_job, read_key, workspace_lock)
from scene_assets import load_scene_jobs


def arguments():
    parser = argparse.ArgumentParser(description="Meshy chess candidates; plan/demo are offline and free")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "demo", "run"):
        child = commands.add_parser(command, help={"plan": "Validate references and estimate (offline)",
            "demo": "Exercise loopback mock API (offline, fixture models only)",
            "run": "Create real paid candidate tasks"}[command])
        child.add_argument("--pieces", default="general_red" if command == "run" else "all",
                           help="pilot, all, or comma-separated asset IDs")
        child.add_argument("--variant", type=int, default=1, help="1..3; same variant resumes, a new one costs credits")
        child.add_argument("--texture-resolution", choices=("2k", "4k", "8k"), help="8k costs 35; 2k/4k cost 30")
        child.add_argument("--save-source", action="store_true", help="Also request/archive the pre-remesh GLB")
        child.add_argument("--target-polycount", type=int, help="Candidate target, 100..300000; verify actual triangles after download")
        child.add_argument("--geometry-master", action="store_true", help="25 credits: Meshy 7 Ultra, untextured native geometry, no remesh; inspect before texturing")
        child.add_argument("--image-enhancement", action=argparse.BooleanOptionalAction, default=None,
                           help="Explicitly enable/disable Meshy's input optimization; included in input fingerprint")
        child.add_argument("--concurrency", type=int, choices=(1, 2, 3), default=1)
        child.add_argument("--reference-views", help="Explicit subset/order: front,side,back; original files stay unchanged")
        child.add_argument("--single-image", action="store_true", help="Use the distinct Image-to-3D endpoint; front view by default")
    for command in ("texture-plan", "texture"):
        child = commands.add_parser(command, help="Retexture an explicit existing GLB; texture-plan is offline")
        child.add_argument("--model", required=True, help="Existing local GLB inside the project; source is not overwritten")
        child.add_argument("--piece", default="general_red")
        child.add_argument("--variant", type=int, default=1)
        child.add_argument("--texture-resolution", choices=("2k", "4k", "8k"), default="8k")
    for command in ("scene-plan", "scene-run"):
        child = commands.add_parser(command, help="Explicit scene manifest; scene-plan is offline")
        child.add_argument("--manifest", default="scripts/meshy/scene-assets.json")
        child.add_argument("--assets", default="all")
        child.add_argument("--variant", type=int, default=1)
        child.add_argument("--concurrency", type=int, choices=(1, 2, 3), default=1)
    for command in ("run", "resume", "texture", "scene-run"):
        child = commands.choices[command] if command in commands.choices else commands.add_parser(command, help="Only poll/download existing tasks")
        child.add_argument("--wait-seconds", type=int, default=1800, help="Per-task polling deadline; resume after timeout")
        child.add_argument("--poll-seconds", type=int, default=10)
    commands.add_parser("balance", help="Read actual Meshy API balance")
    commands.add_parser("status", help="Read local credit ledger (offline)")
    tasks = commands.add_parser("tasks", help="Read remote task names/IDs to reconcile an uncertain POST")
    tasks.add_argument("--page", type=int, default=1)
    tasks.add_argument("--operation", choices=("generation", "single-image", "texture"), default="generation")
    recover = commands.add_parser("reconcile", help="Attach a verified existing task ID; no paid submission")
    recover.add_argument("--piece", required=True)
    recover.add_argument("--variant", type=int, default=1)
    recover.add_argument("--task-id", required=True)
    recover.add_argument("--operation", choices=("generation", "texture"), default="generation")
    return parser.parse_args()


def main():
    # Windows terminals and redirected reports should both preserve Chinese paths.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = arguments()
    state_dir = ROOT / ".meshy/live"
    if args.command == "status":
        path = state_dir / "ledger.json"
        if not path.exists():
            print("No live ledger found in this workspace.")
            return
        ledger = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps({"budget": BUDGET, "balance_floor": BALANCE_FLOOR,
            "spent_or_reserved": sum(job["held_credits"] for job in ledger["jobs"].values()),
            "jobs": [{key: record.get(key) for key in ("key", "name", "task_id", "state", "held_credits", "archived")}
                     for record in ledger["jobs"].values()]}, ensure_ascii=False, indent=2))
        return
    if args.command in {"plan", "demo", "run"}:
        jobs = load_jobs(args.pieces, args.variant, texture_resolution=args.texture_resolution,
                         save_source=args.save_source, target_polycount=args.target_polycount,
                         geometry_master=args.geometry_master, image_enhancement=args.image_enhancement,
                         reference_views=args.reference_views, single_image=args.single_image)
    if args.command in {"texture-plan", "texture"}:
        jobs = [load_retexture_job(args.model, args.piece, args.variant,
                                  texture_resolution=args.texture_resolution)]
    if args.command in {"scene-plan", "scene-run"}:
        jobs = load_scene_jobs(args.manifest, args.assets, args.variant)
    if args.command == "scene-plan":
        atomic_json(ROOT / ".meshy/scene-plan.json", {"offline": True, "jobs": jobs})
        for job in jobs:
            print(f"{job['key']}: {job['estimate']} credits if new")
        print(f"Total if new: {sum(job['estimate'] for job in jobs)}; no network requests")
        return
    if args.command == "texture-plan":
        atomic_json(ROOT / ".meshy/texture-plan.json", {"offline": True, "job": jobs[0]})
        print(f"Existing geometry: {jobs[0]['model']['path']}")
        print(f"New UV + {args.texture_resolution} PBR with 3 reference views; {jobs[0]['estimate']} credits if new.")
        print("No network requests. Full metadata: " + str(ROOT / ".meshy/texture-plan.json"))
        return
    if args.command == "plan":
        report = {"offline": True, "price_checked": PRICE_DATE, "count": len(jobs),
                  "estimated_if_all_new": sum(job["estimate"] for job in jobs),
                  "project_cap": BUDGET, "account_balance_floor": BALANCE_FLOOR,
                  "jobs": jobs}
        atomic_json(ROOT / ".meshy/plan.json", report)
        print(f"Validated {len(jobs)} pieces / {sum(len(job['images']) for job in jobs)} separate view images.")
        for job in jobs:
            if args.geometry_master:
                print(f"  {job['key']}: {job['estimate']} credits, Ultra native geometry, no texture/remesh")
            else:
                print(f"  {job['key']}: {job['estimate']} credits, {job['params']['texture_resolution']}, target {job['params']['target_polycount']} triangles")
        print(f"If all new: {report['estimated_if_all_new']} credits. Cap {BUDGET}; keep {BALANCE_FLOOR} account credits.")
        print("No network requests. Full request metadata (without image base64): " + str(ROOT / ".meshy/plan.json"))
        return
    if args.command == "demo":
        from mock_server import mock_server
        directory = ROOT / ".meshy/demo"
        directory.mkdir(parents=True, exist_ok=True)
        run_dir = type(directory)(tempfile.mkdtemp(prefix="run-", dir=directory))
        print("OFFLINE MOCK ONLY: downloaded GLBs are triangle test fixtures, not generated chess models.")
        with mock_server() as server, workspace_lock(run_dir):
            if args.geometry_master:
                server.consumed = 25
            client = Client("mock-key", test_base=server.base, sleep=lambda _: None)
            pipeline = Pipeline(client, run_dir, run_dir / "fixtures", sleep=lambda _: None, poll_seconds=0)
            pipeline.run_batch(jobs, args.concurrency) if args.concurrency > 1 else pipeline.run(jobs)
            before = len(server.posts)
            pipeline = Pipeline(client, run_dir, run_dir / "fixtures", sleep=lambda _: None, poll_seconds=0)
            pipeline.run_batch(jobs, args.concurrency) if args.concurrency > 1 else pipeline.run(jobs)
            if len(server.posts) != before:
                raise PipelineError("Offline rerun unexpectedly created duplicate tasks")
            report = {"mode": "OFFLINE MOCK - NOT GENERATED ASSETS", "real_credits_spent": 0,
                      "pieces": len(jobs), "mock_posts": len(server.posts), "duplicate_posts_on_rerun": 0,
                      "mock_balance": server.balance, "result": "passed"}
            atomic_json(run_dir / "demo-report.json", report)
            print(json.dumps(report, indent=2))
        print("Demo files: " + str(run_dir))
        return
    client = Client(read_key(), timeout=120 if args.command in {"texture", "scene-run"} else 60)
    if args.command == "balance":
        print(f"Meshy API balance: {client.balance()} credits")
        return
    if args.command == "tasks":
        endpoint = {"generation": ENDPOINT, "single-image": SINGLE_IMAGE, "texture": RETEXTURE}[args.operation]
        tasks = client.tasks(args.page, endpoint)
        print(json.dumps([{key: item.get(key) for key in ("id", "name", "status", "consumed_credits")}
                          for item in tasks], ensure_ascii=False, indent=2))
        return
    if args.command in {"run", "resume", "texture", "scene-run"} and (args.wait_seconds < 1 or args.poll_seconds < 1):
        raise PipelineError("wait-seconds and poll-seconds must be positive")
    with workspace_lock(state_dir):
        pipeline = Pipeline(client, state_dir, ROOT / "assets/generated/meshy",
                            wait_seconds=getattr(args, "wait_seconds", 1800),
                            poll_seconds=getattr(args, "poll_seconds", 10))
        if args.command in {"run", "texture", "scene-run"}:
            print("LIVE PAID RUN. Candidates will be archived for review under assets/generated/meshy.")
            pipeline.run_batch(jobs, args.concurrency) if getattr(args, "concurrency", 1) > 1 else pipeline.run(jobs)
        elif args.command == "resume":
            pipeline.resume()
        elif args.command == "reconcile":
            operation = "/texture" if args.operation == "texture" else ""
            pipeline.reconcile(f"{args.piece}{operation}/v{args.variant}", args.task_id)
            print("Task attached. Run resume to poll and archive it without creating a new task.")


if __name__ == "__main__":
    try:
        main()
    except (PipelineError, OSError, ValueError) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Interrupted. Keep .meshy/live/ledger.json; use status/resume before restarting.", file=sys.stderr)
        sys.exit(130)
