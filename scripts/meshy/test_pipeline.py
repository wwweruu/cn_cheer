"""Offline protocol, budget and recovery tests. No Meshy key or internet required."""
from __future__ import annotations

import json
import base64
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from mock_server import fixture_glb, mock_server
from pipeline import (ApiError, Client, Pipeline, PipelineError, ROOT, atomic_json,
                      RETEXTURE, credit, estimate, inspect_glb, load_jobs, load_retexture_job,
                      read_key, workspace_lock)
from scene_assets import load_scene_jobs


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        config = json.loads((ROOT / "scripts/meshy/pieces.json").read_text(encoding="utf-8"))
        atomic_json(self.root / "scripts/meshy/pieces.json", config)
        for piece in config["pieces"]:
            for index, view in enumerate(config["views"]):
                path = self.root / config["reference_root"] / piece["reference"] / view
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"\xff\xd8\xff" + bytes([index]) + piece["id"].encode())
        self.jobs = load_jobs("all", root=self.root)
        self.state_dir = self.root / "state"
        self.output_dir = self.root / "output"

    def pipeline(self, server, **kwargs):
        client = Client("mock-key", test_base=server.base, sleep=lambda _: None)
        return Pipeline(client, self.state_dir, self.output_dir, root=self.root,
                        sleep=lambda _: None, poll_seconds=0, emit=lambda _: None, **kwargs)

    def scene_job(self, kind="image", **fields):
        entry = {"id": "ground_test", "kind": kind, "prompt": "Weathered ochre surface", **fields}
        atomic_json(self.root / "scene.json", {"assets": [entry]})
        return load_scene_jobs("scene.json", root=self.root)[0]

    def test_image_task_archives_and_restarts_without_model_or_duplicate_post(self):
        job = self.scene_job(remove_background=True)
        with mock_server() as server:
            server.consumed = 9
            self.pipeline(server).run([job])
            self.pipeline(server).run_batch([job])
            self.assertEqual(len(server.posts), 1)
            self.assertEqual(server.balance, 2991)
            self.assertNotIn("name", server.posts[0]["payload"])
            self.assertTrue(server.posts[0]["payload"]["remove_background"])
            self.assertTrue((self.output_dir / job["key"] / "image.png").is_file())
            self.assertFalse((self.output_dir / job["key"] / "model.glb").exists())

    def test_image_edit_input_hash_and_endpoint_are_verified(self):
        reference = self.jobs[0]["images"][0]["path"]
        job = self.scene_job(references=[reference])
        with mock_server() as server:
            server.consumed = 9
            self.pipeline(server).run([job])
            self.assertTrue(server.posts[0]["path"].endswith("/image-to-image"))
            self.assertTrue(server.posts[0]["payload"]["reference_image_urls"][0].startswith("data:image/jpeg;base64,"))
        (self.root / reference).write_bytes(b"\xff\xd8\xffchanged")
        with mock_server() as server:
            pipeline = self.pipeline(server)
            pipeline.ledger["jobs"] = {}
            with self.assertRaisesRegex(PipelineError, "Reference changed"):
                pipeline.submit(job)
            self.assertEqual(len(server.posts), 0)

    def test_image_unknown_post_reconciles_by_prompt_model_time(self):
        job = self.scene_job()
        with mock_server() as server:
            server.consumed = 9
            server.post_status, server.accept_then_fail = 503, True
            pipeline = self.pipeline(server)
            with self.assertRaisesRegex(PipelineError, "UNKNOWN"):
                pipeline.run([job])
            task_id = next(iter(server.tasks))
            server.tasks[task_id]["prompt"] = "unrelated"
            with self.assertRaises(PipelineError):
                pipeline.reconcile(job["key"], task_id)
            server.tasks[task_id]["prompt"] = job["params"]["prompt"]
            pipeline.reconcile(job["key"], task_id)
            pipeline.resume()
            self.assertEqual(len(server.posts), 1)

    def test_scene_surface_preserves_uv_and_uses_only_text_style(self):
        (self.root / "carrier.glb").write_bytes(fixture_glb())
        job = self.scene_job("surface", model="carrier.glb")
        with mock_server() as server:
            server.consumed = 10
            self.pipeline(server).run([job])
            payload = server.posts[0]["payload"]
            self.assertTrue(payload["enable_original_uv"])
            self.assertEqual(payload["texture_resolution"], "4k")
            self.assertNotIn("multiview_image_urls", payload)
            self.assertEqual(server.balance, 2990)

    def test_image_price_increase_stops_next_operation_in_shared_ledger(self):
        job = self.scene_job()
        with mock_server() as server:
            server.consumed = 12
            with self.assertRaisesRegex(PipelineError, "credits"):
                self.pipeline(server).run_batch([job, self.jobs[0]], max_active=1)
            self.assertEqual(len(server.posts), 1)
            self.assertTrue(self.pipeline(server).ledger["jobs"][job["key"]]["archived"])

    def test_scene_8k_board_profile_and_input_restrictions(self):
        reference = self.jobs[0]["images"][0]["path"]
        job = self.scene_job("geometry", references=[reference])
        self.assertEqual(job["estimate"], 35)
        self.assertEqual(job["params"]["texture_resolution"], "8k")
        self.assertFalse(job["params"]["should_remesh"])
        with self.assertRaises(PipelineError):
            self.scene_job("geometry", references=[reference, reference])
        with self.assertRaises(PipelineError):
            self.scene_job(references=[reference] * 6)

    def test_all_fourteen_requests_and_resume_without_duplicate_posts(self):
        with mock_server() as server:
            pipeline = self.pipeline(server)
            pipeline.run(self.jobs)
            self.assertEqual(len(server.posts), 14)
            self.assertEqual(server.balance, 2580)
            self.assertEqual(pipeline.committed(), 420)
            # Restart from disk and run all again: no paid retries or asset downloads.
            downloads = sum("/assets/" in item["path"] for item in server.requests)
            self.pipeline(server).run(self.jobs)
            self.assertEqual(len(server.posts), 14)
            self.assertEqual(sum("/assets/" in item["path"] for item in server.requests), downloads)
            for request in server.posts:
                self.assertEqual(request["path"], "/openapi/v1/multi-image-to-3d")
                self.assertEqual(request["authorization"], "Bearer mock-key")
                payload = request["payload"]
                self.assertEqual(len(payload["image_urls"]), 3)
                self.assertTrue(all(uri.startswith("data:image/jpeg;base64,") for uri in payload["image_urls"]))
                self.assertEqual(payload["ai_model"], "meshy-7")
                self.assertFalse(payload["ultra_mode"])
                self.assertEqual(payload["target_formats"], ["glb"])
                self.assertEqual(payload["texture_resolution"], "2k")
            self.assertTrue(all(not request["authorization"] for request in server.requests if "/assets/" in request["path"]))
            for job in self.jobs:
                report = json.loads((self.output_dir / job["key"] / "inspection.json").read_text())
                self.assertEqual(report["environment"], "mock")
                self.assertFalse(report["production_accepted"])
            ledger_text = pipeline.path.read_text(encoding="utf-8")
            self.assertNotIn("mock-key", ledger_text)
            self.assertNotIn("base64,", ledger_text)

    def test_batch_limits_active_jobs_and_restart_does_not_duplicate(self):
        with mock_server() as server:
            pipeline = self.pipeline(server)
            jobs = self.jobs[:5]
            original_submit = pipeline.submit
            observed = []
            def submit(job):
                active = sum(record["state"] in {"SUBMITTED", "PENDING", "IN_PROGRESS"}
                             for record in pipeline.ledger["jobs"].values())
                observed.append(active)
                return original_submit(job)
            pipeline.submit = submit
            pipeline.run_batch(jobs, 3)
            self.assertEqual(observed, [0, 1, 2, 0, 1])
            self.assertEqual(len(server.posts), 5)
            self.pipeline(server).run_batch(jobs, 3)
            self.assertEqual(len(server.posts), 5)

    def test_batch_restart_resumes_inflight_before_new_spending(self):
        with mock_server() as server:
            server.polls_until_done = 10
            with self.assertRaisesRegex(PipelineError, "deadline"):
                self.pipeline(server, wait_seconds=0).run_batch(self.jobs[:5], 3)
            self.assertEqual(len(server.posts), 3)
            server.polls_until_done = 0
            self.pipeline(server).run_batch(self.jobs[:5], 3)
            self.assertEqual(len(server.posts), 5)

    def test_batch_unknown_post_stops_entire_batch_and_rerun(self):
        with mock_server() as server:
            server.post_status, server.accept_then_fail = 503, True
            with self.assertRaisesRegex(PipelineError, "UNKNOWN"):
                self.pipeline(server).run_batch(self.jobs[:5], 3)
            self.assertEqual(len(server.posts), 1)
            with self.assertRaisesRegex(PipelineError, "Uncertain"):
                self.pipeline(server).run_batch(self.jobs[:5], 3)
            self.assertEqual(len(server.posts), 1)

    def test_batch_price_mismatch_stops_waiting_jobs(self):
        with mock_server() as server:
            server.consumed = 35
            with self.assertRaisesRegex(PipelineError, "Unexpected reported credits"):
                self.pipeline(server).run_batch(self.jobs[:5], 2)
            self.assertEqual(len(server.posts), 2)

    def test_explicit_image_enhancement_is_fingerprinted(self):
        plain = load_jobs("general_black", root=self.root, geometry_master=True)[0]
        enhanced = load_jobs("general_black", root=self.root, geometry_master=True,
                             image_enhancement=True)[0]
        self.assertFalse(plain["params"]["image_enhancement"])
        self.assertTrue(enhanced["params"]["image_enhancement"])
        self.assertNotEqual(plain["fingerprint"], enhanced["fingerprint"])
        self.assertEqual(plain["images"], enhanced["images"])
        self.assertEqual(enhanced["estimate"], 25)

    def test_single_reference_is_explicit_and_retains_source_hash(self):
        full = load_jobs("general_black", root=self.root, geometry_master=True)[0]
        front = load_jobs("general_black", root=self.root, geometry_master=True, reference_views="front")[0]
        self.assertEqual(front["images"], full["images"][:1])
        self.assertNotEqual(full["fingerprint"], front["fingerprint"])
        with self.assertRaises(PipelineError):
            load_jobs("general_black", root=self.root, reference_views="front,front")

    def test_image_endpoint_payload_and_resume_use_same_endpoint(self):
        with mock_server() as server:
            server.consumed = 25
            job = load_jobs("general_black", root=self.root, geometry_master=True, single_image=True)[0]
            self.assertEqual(len(job["images"]), 1)
            self.pipeline(server).run([job])
            self.pipeline(server).run([job])
            self.assertEqual(len(server.posts), 1)
            self.assertEqual(server.posts[0]["path"], "/openapi/v1/image-to-3d")
            self.assertIn("image_url", server.posts[0]["payload"])
            self.assertNotIn("image_urls", server.posts[0]["payload"])
            self.assertFalse(any("multi-image-to-3d" in req["path"] for req in server.requests))
        with self.assertRaises(PipelineError):
            load_jobs("general_black", root=self.root, single_image=True, reference_views="front,back")

    def test_front_view_order_and_model_manifest_coverage(self):
        source = (ROOT / "src/assets/manifest.ts").read_text(encoding="utf-8")
        self.assertEqual(len(self.jobs), 14)
        self.assertEqual(sum(job["estimate"] for job in self.jobs), 420)
        for job in self.jobs:
            self.assertIn('"' + job["piece"] + '"', source)
            self.assertTrue(job["images"][0]["path"].endswith("正面.jpg"))
        self.assertEqual({job["piece"] for job in load_jobs("pilot", root=self.root)},
                         {"general_red", "horse_red", "cannon_red"})

    def test_batch_preflight_refuses_to_spend_over_project_cap(self):
        with mock_server() as server:
            pipeline = self.pipeline(server)
            pipeline.ledger["jobs"]["old"] = {"held_credits": 1400, "state": "SUCCEEDED"}
            with self.assertRaisesRegex(PipelineError, "exceeds"):
                pipeline.run(self.jobs)
            self.assertEqual(server.posts, [])

    def test_account_reserve_blocks_whole_batch_without_partial_spending(self):
        with mock_server() as server:
            server.balance = 1500  # Enough for several, but not all 14 while retaining 1200.
            with self.assertRaisesRegex(PipelineError, "less than 1200"):
                self.pipeline(server).run(self.jobs)
            self.assertEqual(server.posts, [])

    def test_balance_rechecked_immediately_before_each_post(self):
        with mock_server() as server:
            pipeline = self.pipeline(server)
            pipeline.preflight(self.jobs)
            server.balance = 1229  # Another application spent credits after preflight.
            with self.assertRaisesRegex(PipelineError, "reserve reached"):
                pipeline.submit(self.jobs[0])
            self.assertEqual(server.posts, [])

    def test_actual_price_increase_archives_current_output_and_stops_batch(self):
        with mock_server() as server:
            server.consumed = 35
            pipeline = self.pipeline(server)
            with self.assertRaisesRegex(PipelineError, "Actual credits differ"):
                pipeline.run(self.jobs)
            self.assertEqual(len(server.posts), 1)
            self.assertEqual(pipeline.committed(), 35)
            self.assertTrue(pipeline.ledger["jobs"][self.jobs[0]["key"]]["archived"])
            with self.assertRaisesRegex(PipelineError, "Price mismatch"):
                self.pipeline(server).run(self.jobs)
            self.assertEqual(len(server.posts), 1)

    def test_accepted_post_with_server_error_is_not_retried_on_restart(self):
        with mock_server() as server:
            server.post_status, server.accept_then_fail = 503, True
            pipeline = self.pipeline(server)
            with self.assertRaisesRegex(PipelineError, "UNKNOWN"):
                pipeline.run(self.jobs)
            self.assertEqual(len(server.posts), 1)
            self.assertEqual(pipeline.committed(), 30)
            with self.assertRaisesRegex(PipelineError, "Uncertain paid submission"):
                self.pipeline(server).run(self.jobs)
            self.assertEqual(len(server.posts), 1)

    def test_malformed_create_response_is_uncertain(self):
        with mock_server() as server:
            server.malformed_post = True
            pipeline = self.pipeline(server)
            with self.assertRaisesRegex(PipelineError, "UNKNOWN"):
                pipeline.run(self.jobs)
            self.assertEqual(len(server.posts), 1)
            self.assertEqual(pipeline.committed(), 30)

    def test_connection_timeout_keeps_reservation(self):
        with mock_server() as server:
            pipeline = self.pipeline(server)
            with patch.object(pipeline.client, "request", side_effect=ApiError()):
                # submit's initial balance read must remain available for this injected POST failure.
                with patch.object(pipeline.client, "balance", return_value=3000):
                    with self.assertRaisesRegex(PipelineError, "UNKNOWN"):
                        pipeline.submit(self.jobs[0])
            self.assertEqual(pipeline.committed(), 30)
            self.assertEqual(pipeline.ledger["jobs"][self.jobs[0]["key"]]["state"], "UNKNOWN")

    def test_crash_between_reservation_and_post_blocks_resubmission(self):
        with mock_server() as server:
            pipeline = self.pipeline(server)
            original_request = pipeline.client.request

            def crash(method, *args):
                if method == "POST":
                    raise KeyboardInterrupt()
                return original_request(method, *args)

            with patch.object(pipeline.client, "request", side_effect=crash):
                with self.assertRaises(KeyboardInterrupt):
                    pipeline.submit(self.jobs[0])
            recovered = self.pipeline(server)
            self.assertEqual(recovered.committed(), 30)
            with self.assertRaisesRegex(PipelineError, "Uncertain paid submission"):
                recovered.run(self.jobs)
            self.assertEqual(len(server.posts), 0)

    def test_explicit_post_rejections_stop_without_retry_and_release_reservation(self):
        for status in (400, 401, 402, 403, 429):
            with self.subTest(status=status), mock_server() as server:
                # Different variant's job key is not needed; each case has an independent ledger.
                self.state_dir = self.root / f"state-{status}"
                server.post_status = status
                pipeline = self.pipeline(server)
                with self.assertRaisesRegex(PipelineError, "REJECTED"):
                    pipeline.run(self.jobs)
                self.assertEqual(pipeline.committed(), 0)
                self.assertEqual(len(server.posts), 1)
                with self.assertRaisesRegex(PipelineError, "previously REJECTED"):
                    self.pipeline(server).run(self.jobs)
                self.assertEqual(len(server.posts), 1)

    def test_failed_task_refunds_only_after_explicit_zero_and_never_auto_regenerates(self):
        with mock_server() as server:
            server.task_status, server.consumed = "FAILED", 0
            pipeline = self.pipeline(server)
            with self.assertRaisesRegex(PipelineError, "FAILED"):
                pipeline.run(self.jobs)
            self.assertEqual(pipeline.committed(), 0)
            self.assertEqual(server.balance, 3000)
            self.assertEqual(len(server.posts), 1)
            server.task_status, server.consumed = "SUCCEEDED", 30
            alternative = load_jobs(self.jobs[0]["piece"], 2, self.root)
            pipeline.run(alternative)
            self.assertEqual(pipeline.committed(), 30)
            self.assertEqual(len(server.posts), 2)

    def test_canceled_missing_credit_and_running_zero_keep_conservative_reservations(self):
        with mock_server() as server:
            server.task_status, server.consumed, server.running_credits = "CANCELED", None, 0
            pipeline = self.pipeline(server)
            record = pipeline.submit(self.jobs[0])
            pipeline.refresh(record)
            self.assertEqual(pipeline.committed(), 30)
            with self.assertRaisesRegex(PipelineError, "CANCELED"):
                pipeline.wait_and_archive(record)
            self.assertEqual(pipeline.committed(), 30)

    def test_poll_timeout_resume_only_gets_existing_task(self):
        with mock_server() as server:
            server.polls_until_done = 50
            pipeline = self.pipeline(server, wait_seconds=0)
            with self.assertRaisesRegex(PipelineError, "Polling deadline"):
                pipeline.run(self.jobs)
            self.assertEqual(len(server.posts), 1)
            server.polls_until_done = 0
            self.pipeline(server).resume()
            self.assertEqual(len(server.posts), 1)
            self.assertTrue((self.output_dir / self.jobs[0]["key"] / "model.glb").exists())

    def test_get_retries_rate_limits_and_transient_errors_but_not_unauthorized(self):
        with mock_server() as server:
            client = Client("mock-key", test_base=server.base, sleep=lambda _: None)
            server.get_failures = [429, 503]
            self.assertEqual(client.balance(), 3000)
            self.assertEqual(len(server.requests), 3)
            server.get_failures = [401]
            with self.assertRaises(ApiError):
                client.balance()
            self.assertEqual(len(server.requests), 4)

    def test_task_listing_respects_ten_item_openapi_limit(self):
        with mock_server() as server:
            client = self.pipeline(server).client
            self.assertEqual(client.tasks(2), [])
            self.assertEqual(server.requests[-1]["path"],
                             "/openapi/v1/multi-image-to-3d?page_num=2&page_size=10&sort_by=-created_at")
            with self.assertRaises(PipelineError):
                client.tasks(0)

    def test_download_failure_resumes_without_regenerating(self):
        with mock_server() as server:
            server.asset_status = 403
            pipeline = self.pipeline(server)
            with self.assertRaisesRegex(PipelineError, "download failed"):
                pipeline.run(self.jobs)
            self.assertEqual(len(server.posts), 1)
            server.asset_status = 200
            self.pipeline(server).resume()
            self.assertEqual(len(server.posts), 1)
            self.assertEqual(len(list(self.output_dir.rglob("*.part"))), 0)

    def test_corrupt_download_is_rejected_then_repaired_without_paid_post(self):
        with mock_server() as server:
            server.model_data = b"<html>expired URL</html>"
            pipeline = self.pipeline(server)
            with self.assertRaisesRegex(PipelineError, "GLB 2.0"):
                pipeline.run(self.jobs)
            record = pipeline.ledger["jobs"][self.jobs[0]["key"]]
            self.assertFalse(record.get("archived"))
            server.model_data = fixture_glb()
            self.pipeline(server).resume()
            self.assertEqual(len(server.posts), 1)
            # Also repair a file corrupted locally after a successful archive.
            (self.output_dir / self.jobs[0]["key"] / "model.glb").write_bytes(b"corrupt")
            self.pipeline(server).resume()
            self.assertEqual(len(server.posts), 1)
            inspect_glb(self.output_dir / self.jobs[0]["key"] / "model.glb")

    def test_reconcile_requires_exact_name_and_recovers_without_post(self):
        with mock_server() as server:
            server.post_status, server.accept_then_fail = 503, True
            pipeline = self.pipeline(server)
            with self.assertRaises(PipelineError):
                pipeline.run(self.jobs)
            key = self.jobs[0]["key"]
            task_id = next(iter(server.tasks))
            actual_name = server.tasks[task_id]["name"]
            server.tasks[task_id]["name"] = "unrelated-task"
            with self.assertRaisesRegex(PipelineError, "match"):
                pipeline.reconcile(key, task_id)
            server.tasks[task_id]["name"] = actual_name
            pipeline.reconcile(key, task_id)
            self.pipeline(server).resume()
            self.assertEqual(len(server.posts), 1)

    def test_changed_input_cannot_silently_reuse_variant(self):
        with mock_server() as server:
            pipeline = self.pipeline(server)
            pipeline.run(self.jobs[:1])
            path = self.root / self.jobs[0]["images"][0]["path"]
            path.write_bytes(path.read_bytes() + b"changed")
            altered = load_jobs(self.jobs[0]["piece"], root=self.root)
            with self.assertRaisesRegex(PipelineError, "changed"):
                self.pipeline(server).run(altered)
            self.assertEqual(len(server.posts), 1)

    def test_missing_reference_blocks_preflight_and_invalid_variants(self):
        (self.root / self.jobs[-1]["images"][2]["path"]).unlink()
        with self.assertRaisesRegex(PipelineError, "Missing reference"):
            load_jobs("all", root=self.root)
        for variant in (0, 4):
            with self.assertRaises(PipelineError):
                load_jobs("pilot", variant, self.root)
        with self.assertRaises(PipelineError):
            load_jobs("unknown", root=self.root)

    def test_unreviewed_pricing_options_are_blocked(self):
        params = self.jobs[0]["params"]
        for name, value in (("ai_model", "latest"), ("ultra_mode", True), ("texture_resolution", "16k"),
                            ("target_formats", ["glb", "fbx"]), ("auto_size", True)):
            with self.subTest(name=name), self.assertRaises(PipelineError):
                estimate({**params, name: value})
        self.assertEqual(estimate({**params, "ai_model": "meshy-6"}), 30)

    def test_high_resolution_pricing_and_source_archive(self):
        with mock_server() as server:
            server.consumed = 35
            job = load_jobs("general_red", root=self.root, texture_resolution="8k",
                            save_source=True, target_polycount=20000)[0]
            self.assertEqual(job["estimate"], 35)
            self.assertEqual(estimate({**job["params"], "texture_resolution": "4k"}), 30)
            pipeline = self.pipeline(server)
            pipeline.run([job])
            self.assertEqual(pipeline.committed(), 35)
            self.assertEqual(server.balance, 2965)
            self.assertTrue((self.output_dir / job["key"] / "source_pre_remeshed.glb").exists())
            self.pipeline(server).run([job])
            self.assertEqual(len(server.posts), 1)
            self.assertEqual(server.posts[0]["payload"]["texture_resolution"], "8k")
            self.assertTrue(server.posts[0]["payload"]["save_pre_remeshed_model"])

    def test_high_resolution_reserves_35_before_any_paid_post(self):
        with mock_server() as server:
            server.balance = 1234
            jobs = load_jobs("general_red", root=self.root, texture_resolution="8k")
            with self.assertRaisesRegex(PipelineError, "less than 1200"):
                self.pipeline(server).run(jobs)
            self.assertEqual(len(server.posts), 0)

    def test_credit_values_fail_closed(self):
        for value in (None, "30", True, -1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(PipelineError):
                credit(value)

    def test_geometry_master_archives_without_textures_and_rerun_is_free(self):
        with mock_server() as server:
            server.consumed = 25
            job = load_jobs("general_red", 2, self.root, geometry_master=True)[0]
            pipeline = self.pipeline(server)
            pipeline.run([job])
            self.assertEqual(pipeline.committed(), 25)
            self.assertEqual(server.balance, 2975)
            payload = server.posts[0]["payload"]
            self.assertTrue(payload["ultra_mode"])
            self.assertFalse(payload["should_remesh"])
            self.assertFalse(payload["should_texture"])
            self.assertEqual(payload["pose_mode"], "")
            self.assertEqual(len(payload["image_urls"]), 3)
            for field in ("target_polycount", "texture_resolution", "topology"):
                self.assertNotIn(field, payload)
            self.assertTrue((self.output_dir / job["key"] / "model.glb").exists())
            self.pipeline(server).run([job])
            self.assertEqual(len(server.posts), 1)

    def test_geometry_master_reservation_and_conflicting_flags(self):
        with mock_server() as server:
            server.balance = 1224
            job = load_jobs("general_red", 2, self.root, geometry_master=True)[0]
            with self.assertRaisesRegex(PipelineError, "less than 1200"):
                self.pipeline(server).run([job])
            self.assertEqual(len(server.posts), 0)
            for flags in ({"texture_resolution": "8k"}, {"target_polycount": 20000}):
                with self.assertRaises(PipelineError):
                    load_jobs("general_red", 2, self.root, geometry_master=True, **flags)

    def test_geometry_master_cannot_overwrite_an_existing_variant(self):
        with mock_server() as server:
            self.pipeline(server).run([self.jobs[0]])
            altered = load_jobs(self.jobs[0]["piece"], root=self.root, geometry_master=True)
            with self.assertRaisesRegex(PipelineError, "changed"):
                self.pipeline(server).run(altered)
            self.assertEqual(len(server.posts), 1)

    def texture_job(self):
        path = self.root / "approved-source.glb"
        path.write_bytes(fixture_glb())
        return load_retexture_job(path, root=self.root)

    def test_retexture_existing_geometry_shares_ledger_and_resumes_without_post(self):
        with mock_server() as server:
            pipeline = self.pipeline(server)
            pipeline.run([self.jobs[0]])
            server.consumed = 15
            job = self.texture_job()
            self.pipeline(server).run([job])
            payload = server.posts[-1]["payload"]
            self.assertEqual(server.posts[-1]["path"], "/openapi/v1/retexture")
            self.assertEqual(base64.b64decode(payload["model_url"].split(",")[1]), fixture_glb())
            self.assertEqual(len(payload["multiview_image_urls"]), 3)
            self.assertFalse(payload["enable_original_uv"])
            self.assertTrue(payload["enable_pbr"])
            self.assertNotIn("should_remesh", payload)
            self.assertNotIn("image_urls", payload)
            self.assertEqual(self.pipeline(server).committed(), 45)
            self.assertEqual(server.balance, 2955)
            self.pipeline(server).run([job])
            self.pipeline(server).resume()
            self.assertEqual(len(server.posts), 2)
            self.assertNotIn("base64,", (self.state_dir / "ledger.json").read_text(encoding="utf-8"))

    def test_retexture_source_change_is_blocked_before_reservation_or_post(self):
        with mock_server() as server:
            job = self.texture_job()
            (self.root / job["model"]["path"]).write_bytes(fixture_glb() + b"changed")
            with self.assertRaisesRegex(PipelineError, "Source geometry changed"):
                self.pipeline(server).run([job])
            self.assertEqual(len(server.posts), 0)
            self.assertEqual(self.pipeline(server).committed(), 0)

    def test_retexture_reserves_15_and_uses_shared_project_cap(self):
        with mock_server() as server:
            job = self.texture_job()
            server.balance = 1214
            with self.assertRaisesRegex(PipelineError, "less than 1200"):
                self.pipeline(server).run([job])
            server.balance = 3000
            pipeline = self.pipeline(server)
            pipeline.ledger["jobs"]["old-generation"] = {"held_credits": 1790, "state": "SUCCEEDED"}
            pipeline.save()
            with self.assertRaisesRegex(PipelineError, "exceeds"):
                self.pipeline(server).run([job])
            self.assertEqual(len(server.posts), 0)

    def test_uncertain_retexture_blocks_generation_and_reconciles_on_correct_endpoint(self):
        with mock_server() as server:
            job = self.texture_job()
            server.post_status, server.accept_then_fail, server.consumed = 503, True, 15
            pipeline = self.pipeline(server)
            with self.assertRaisesRegex(PipelineError, "UNKNOWN"):
                pipeline.run([job])
            with self.assertRaisesRegex(PipelineError, "Uncertain"):
                self.pipeline(server).run([self.jobs[0]])
            task = pipeline.client.tasks(endpoint=RETEXTURE)[0]
            self.assertEqual(pipeline.client.tasks(), [])
            self.pipeline(server).reconcile(job["key"], task["id"])
            self.pipeline(server).resume()
            self.assertEqual(len(server.posts), 1)
            self.assertEqual(self.pipeline(server).committed(), 15)
            self.assertTrue((self.output_dir / job["key"] / "model.glb").exists())

    def test_large_asset_ranges_are_exact_and_do_not_send_api_authorization(self):
        with mock_server() as server, patch("pipeline.RANGE_THRESHOLD", 64), patch("pipeline.RANGE_BYTES", 64):
            path = self.root / "range.glb"
            self.pipeline(server).client.download(server.origin + "/assets/model.glb", path)
            self.assertEqual(path.read_bytes(), fixture_glb())
            ranged = [item for item in server.requests if item.get("range")]
            self.assertGreater(len(ranged), 1)
            self.assertTrue(all(not item["authorization"] for item in ranged))

    def test_wrong_asset_range_is_not_archived_or_left_as_complete_file(self):
        with mock_server() as server, patch("pipeline.RANGE_THRESHOLD", 64), patch("pipeline.RANGE_BYTES", 64):
            server.bad_content_range = True
            path = self.root / "range.glb"
            with self.assertRaisesRegex(PipelineError, "requested byte range"):
                self.pipeline(server).client.download(server.origin + "/assets/model.glb", path)
            self.assertFalse(path.exists())
            self.assertFalse(path.with_suffix(".glb.part").exists())

    def test_malformed_ledger_is_not_reset(self):
        self.state_dir.mkdir()
        (self.state_dir / "ledger.json").write_text("{truncated", encoding="utf-8")
        with mock_server() as server, self.assertRaises(ValueError):
            self.pipeline(server)

    def test_failed_reservation_write_prevents_post(self):
        with mock_server() as server:
            pipeline = self.pipeline(server)
            with patch.object(pipeline, "save", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    pipeline.submit(self.jobs[0])
            self.assertEqual(len(server.posts), 0)

    def test_workspace_lock_is_exclusive_and_released(self):
        with workspace_lock(self.state_dir):
            with self.assertRaisesRegex(PipelineError, "Another Meshy process"):
                with workspace_lock(self.state_dir):
                    self.fail("Second lock unexpectedly acquired")
        with workspace_lock(self.state_dir):
            pass

    def test_secret_loading_without_frontend_key_or_environment_mutation(self):
        (self.root / ".env").write_text('VITE_MESHY_API_KEY=msy_wrong\nMESHY_API_KEY="msy_test_dummy"\n', encoding="utf-8-sig")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(read_key(self.root), "msy_test_dummy")
            self.assertNotIn("MESHY_API_KEY", os.environ)
        (self.root / ".env").write_text("VITE_MESHY_API_KEY=msy_wrong\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(PipelineError):
            read_key(self.root)

    def test_test_origin_cannot_receive_real_key(self):
        with self.assertRaises(PipelineError):
            Client("msy_secret", test_base="http://127.0.0.1:1234/openapi/v1")
        with self.assertRaises(PipelineError):
            Client("mock-key", test_base="https://example.com/openapi/v1")

    def test_asset_host_guard(self):
        with mock_server() as server:
            client = self.pipeline(server).client
            for url in ("https://example.com/model.glb", "http://assets.meshy.ai/file", "file:///etc/passwd"):
                with self.subTest(url=url), self.assertRaisesRegex(PipelineError, "Unexpected asset host"):
                    client.download(url, self.root / "test.glb")

    def test_glb_checks_truncation_and_external_dependencies(self):
        path = self.root / "model.glb"
        path.write_bytes(fixture_glb()[:-1])
        with self.assertRaises(PipelineError):
            inspect_glb(path)
        doc = {"asset": {"version": "2.0"}, "meshes": [{"primitives": [{"attributes": {}}]}],
               "images": [{"uri": "external.png"}]}
        data = json.dumps(doc).encode()
        data += b" " * (-len(data) % 4)
        path.write_bytes(struct.pack("<4sIII4s", b"glTF", 2, len(data) + 20, len(data), b"JSON") + data)
        with self.assertRaisesRegex(PipelineError, "external file"):
            inspect_glb(path)


if __name__ == "__main__":
    unittest.main()
