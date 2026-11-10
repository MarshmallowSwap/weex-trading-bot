"""Offline-only missing-TP simulation. No WEEX credentials or network."""
import json
import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path
from weex_bot_tp_audit import inspect

class FakeReader:
    def __init__(self, positions, regular, algos):
        self.rows = (positions, regular, algos)
    def account(self):
        return self.rows

class MissingTpSimulation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with closing(sqlite3.connect(self.root/'weex_user_live_lifecycle.sqlite3')) as db, db:
            db.executescript("""
            CREATE TABLE trades_v1(id TEXT, symbol TEXT, state TEXT, owned TEXT, plan TEXT);
            CREATE TABLE writes_v1(trade_id TEXT, kind TEXT, state TEXT, response TEXT);
            """)
            db.execute("INSERT INTO trades_v1 VALUES (?,?,?,?,?)", (
                'synthetic_ltc_trade','LTCUSDT','REVIEW_REQUIRED',
                json.dumps({'positionId':'synthetic_position','entryOrderId':'synthetic_entry','entrySource':'automatic'}),
                json.dumps({'entrySource':'automatic'})))
            db.execute("INSERT INTO writes_v1 VALUES (?,?,?,?)", (
                'synthetic_ltc_trade','ENTRY','RESPONSE_RECEIVED',
                json.dumps({'success':True,'orderId':'synthetic_entry'})))
        self.position = {'id':'synthetic_position','symbol':'LTCUSDT','side':'LONG','size':'1'}
        self.tp = {'algoId':'synthetic_tp','symbol':'LTCUSDT','side':'SELL',
                   'positionSide':'LONG','orderType':'TAKE_PROFIT_MARKET',
                   'algoStatus':'NEW','reduceOnly':True,'closePosition':False,'quantity':'1'}

    def status(self, algos=None, regular=None):
        rows = inspect(self.root, FakeReader([self.position], regular or [], algos or []))
        self.assertEqual(len(rows),1)
        return rows[0]['status']

    def test_present(self):
        self.assertEqual(self.status([self.tp]),'TP_PRESENT')

    def test_missing_with_verified_entry(self):
        self.assertEqual(self.status(),'TP_MISSING_RECONCILE_REQUIRED')

    def test_missing_after_prior_tp_dispatch(self):
        with closing(sqlite3.connect(self.root/'weex_user_live_lifecycle.sqlite3')) as db, db:
            db.execute("INSERT INTO writes_v1 VALUES (?,?,?,?)",(
                'synthetic_ltc_trade','TP','RESPONSE_RECEIVED',
                json.dumps([{'success':True,'orderId':'synthetic_tp'}])))
        self.assertEqual(self.status(),'REVIEW_PRIOR_TP_DISPATCH_RECONCILE_HISTORY')

    def test_other_open_order_blocks(self):
        self.assertEqual(self.status(regular=[{'symbol':'LTCUSDT','orderId':'unknown'}]),
                         'REVIEW_AMBIGUOUS_ORDERS')

    def test_entry_not_verified_blocks(self):
        with closing(sqlite3.connect(self.root/'weex_user_live_lifecycle.sqlite3')) as db, db:
            db.execute("UPDATE writes_v1 SET response=? WHERE kind='ENTRY'",
                       (json.dumps({'success':False}),))
        self.assertEqual(self.status(),'REVIEW_ENTRY_OWNERSHIP_UNVERIFIED')

    def test_manual_position_excluded(self):
        with closing(sqlite3.connect(self.root/'weex_user_live_lifecycle.sqlite3')) as db, db:
            db.execute("UPDATE trades_v1 SET plan=?",
                       (json.dumps({'entrySource':'manual_telegram'}),))
            db.execute("UPDATE trades_v1 SET owned=?",
                       (json.dumps({'positionId':'synthetic_position','entrySource':'manual_telegram'}),))
        self.assertEqual(inspect(self.root,FakeReader([self.position],[],[])),[])

if __name__ == '__main__':
    unittest.main()
