"""Paid rig/motion boundary, archive and interrupted-request recovery checks."""
import tempfile
import unittest
from pathlib import Path

from mock_server import fixture_glb, mock_server
from motion_assets import motion_job
from pipeline import Client, Pipeline, PipelineError, make_payload


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "body.glb").write_bytes(fixture_glb())

    def job(self, op="rig", **kw):
        return motion_job("soldier_red", op, model="body.glb", rig_task_id="known-rig", root=self.root, **kw)

    def pipeline(self, server):
        return Pipeline(Client("mock-key", test_base=server.base, sleep=lambda _: None),
                        self.root / "state", self.root / "out", root=self.root,
                        sleep=lambda _: None, poll_seconds=0, emit=lambda _: None)

    def test_payloads_omit_undocumented_fields(self):
        rig = make_payload(self.job(), "local-name", self.root)
        self.assertEqual(set(rig), {"height_meters", "model_url"})
        self.assertTrue(rig["model_url"].startswith("data:application/octet-stream;base64,"))
        clip = make_payload(self.job("idle"), "local-name", self.root)
        self.assertEqual(clip, {"rig_task_id": "known-rig", "action_id": 0})

    def test_modified_upload_stops_before_post(self):
        job = self.job()
        (self.root / "body.glb").write_bytes(b"changed")
        with mock_server() as server:
            with self.assertRaisesRegex(PipelineError, "changed"):
                self.pipeline(server).submit(job)
            self.assertEqual(len(server.posts), 0)

    def test_prices_archive_and_idempotent_resume(self):
        for operation, amount in (("rig", 5), ("idle", 3)):
            with self.subTest(operation=operation), mock_server() as server:
                server.consumed = amount
                job = self.job(operation)
                self.pipeline(server).run([job])
                self.pipeline(server).run([job])
                self.assertEqual(len(server.posts), 1)
                self.assertEqual(server.balance, 3000 - amount)
                folder = self.root / "out" / job["key"]
                self.assertTrue((folder / "model.glb").is_file())
                self.assertTrue((folder / ("rigged.fbx" if operation == "rig" else "animation.fbx")).is_file())

    def test_unknown_rig_blocks_all_new_posts_and_cannot_guess_reconcile(self):
        with mock_server() as server:
            server.consumed = 5
            server.post_status, server.accept_then_fail = 503, True
            pipe = self.pipeline(server)
            with self.assertRaisesRegex(PipelineError, "UNKNOWN"):
                pipe.run([self.job()])
            with self.assertRaises(PipelineError):
                pipe.run([self.job("idle")])
            with self.assertRaises(PipelineError):
                pipe.reconcile(self.job()["key"], next(iter(server.tasks)))
            self.assertEqual(len(server.posts), 1)

    def test_bad_height_and_nonhumanoids_rejected(self):
        for value in (-1, 0, float("nan"), float("inf"), True):
            with self.assertRaises(PipelineError):
                self.job(height=value)
        with self.assertRaises(PipelineError):
            motion_job("horse_red", "rig", model="body.glb", root=self.root)


if __name__ == "__main__":
    unittest.main()
