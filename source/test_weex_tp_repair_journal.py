"""Offline idempotence and failure tests for TP recovery proposals."""
import tempfile
import unittest
from pathlib import Path
from weex_tp_repair_journal import record

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.proposal={'eligible':True,'dispatchAllowed':False,'tradeId':'synthetic',
                       'symbol':'LTCUSDT','positionId':'position1','reason':'CANCELLED_TP_CONFIRMED_PROPOSAL_ONLY'}
    def test_single_proposal_survives_reopen(self):
        a=record(self.root,self.proposal)
        b=record(self.root,self.proposal)
        self.assertEqual(a['state'],'PROPOSED')
        self.assertEqual(b['state'],'ALREADY_PROPOSED')
        self.assertFalse(a['dispatchAllowed'])
        self.assertFalse(b['dispatchAllowed'])
    def test_changed_position_blocks(self):
        record(self.root,self.proposal)
        altered=dict(self.proposal,positionId='different')
        self.assertEqual(record(self.root,altered)['state'],'REVIEW_PROPOSAL_CHANGED')
    def test_no_proposal_on_blocked_gate(self):
        with self.assertRaises(ValueError):
            record(self.root,dict(self.proposal,eligible=False))
        self.assertFalse((self.root/'weex_user_tp_repair_proposals.sqlite3').exists())
    def test_dispatch_permission_must_be_false(self):
        with self.assertRaises(ValueError):
            record(self.root,dict(self.proposal,dispatchAllowed=True))

if __name__=='__main__':
    unittest.main()
