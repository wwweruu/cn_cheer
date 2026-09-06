"""Native motion transport, durable billing and skeleton compatibility checks."""
from test_motion import MotionTests
from native_motion import native_job
from pipeline import ANIMATION, RIGGING, TEXT_MOTION, PipelineError, make_payload
from mock_server import mock_server


class NativeMotionTests(MotionTests):
    def generated(self, **changes):
        spec = {'piece': 'shared-motion', 'role': 'walk', 'operation': 'generate',
                'prompt': 'A guard walks naturally.', 'mode': 'prime', 'duration': 4}
        return native_job({**spec, **changes}, {'jobs': {}}, self.root)

    def test_motion_without_mesh_archives_and_resumes_without_spending(self):
        for mode, cost, extension in [('prime', 10, 'fbx'), ('swift', 3, 'bvh')]:
            with self.subTest(mode=mode), mock_server() as server:
                server.consumed = cost
                job = self.generated(mode=mode, role=mode)
                self.assertEqual(make_payload(job, 'unused'), job['params'])
                pipe = self.pipeline(server)
                pipe.run([job])
                self.pipeline(server).run([job])
                self.assertEqual(len(server.posts), 1)
                self.assertEqual(server.balance, 3000 - cost)
                self.assertTrue((self.root / 'out' / job['key'] / ('motion.' + extension)).exists())
                self.assertTrue(pipe.locally_complete(pipe.ledger['jobs'][job['key']]))

    def test_motion_rejection_bounds_and_credit_guard(self):
        for changes in ({'duration': 4.2}, {'duration': float('nan')}, {'prompt': ''}, {'mode': 'unknown'}):
            with self.assertRaises(PipelineError):
                self.generated(**changes)
        with mock_server() as server:
            server.balance = 1209
            with self.assertRaises(PipelineError):
                self.pipeline(server).run([self.generated()])
            self.assertEqual(len(server.posts), 0)

    def test_quadruped_param_and_retarget_compatibility(self):
        spec = {'piece': 'horse_red', 'role': 'animal', 'operation': 'rig', 'model': 'body.glb', 'height': .8, 'skeleton': 'quadruped'}
        rig = native_job(spec, {'jobs': {}}, self.root)
        self.assertEqual(make_payload(rig, 'unused', self.root)['animation_type'], 'quadruped')
        ledger = {'jobs': {'rig': {**rig, 'task_id': 'rig-task', 'state': 'SUCCEEDED'},
                           'motion': {'endpoint': TEXT_MOTION, 'state': 'SUCCEEDED', 'task_id': 'motion-task'}}}
        request = {'piece': 'horse_red', 'role': 'animal', 'operation': 'walk', 'rig_key': 'rig', 'motion_key': 'motion'}
        with self.assertRaises(PipelineError):
            native_job(request, ledger, self.root)
        ledger['jobs']['rig']['params']['animation_type'] = 'biped'
        animated = native_job(request, ledger, self.root)
        self.assertEqual(animated['params'], {'rig_task_id': 'rig-task', 'motion_task_id': 'motion-task'})
        with self.assertRaises(PipelineError):
            native_job({**request, 'action_id': 0}, ledger, self.root)
