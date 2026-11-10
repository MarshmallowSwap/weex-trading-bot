"""Offline shared-worker-lock TP repair preflight tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from weex_execution_cycle import exclusive
from weex_tp_repair_preflight import preflight

class PreflightLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def test_worker_lock_blocks_parallel_repair(self):
        with exclusive(self.root/'weex_live_worker.lock'):
            with self.assertRaisesRegex(RuntimeError,'CYCLE_ALREADY_RUNNING'):
                preflight(self.root)
    def test_release_lock_on_planning_error(self):
        with patch('weex_tp_repair_preflight.plan',side_effect=ValueError('SIMULATED_FAILURE')):
            with self.assertRaisesRegex(ValueError,'SIMULATED_FAILURE'):
                preflight(self.root)
        with patch('weex_tp_repair_preflight.plan',return_value=[]) as fake:
            self.assertEqual(preflight(self.root),[])
            fake.assert_called_once()
    def test_no_writes_from_preflight(self):
        with patch('weex_tp_repair_preflight.plan',return_value=[]) as fake:
            preflight(self.root,save_proposals=False)
            self.assertFalse((self.root/'weex_user_tp_repair_proposals.sqlite3').exists())
            self.assertEqual(fake.call_args.kwargs['save_proposals'],False)

if __name__=='__main__':
    unittest.main()
