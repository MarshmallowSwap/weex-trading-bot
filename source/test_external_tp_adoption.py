import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from weex_external_tp_adoption import verify

class ExternalTpAdoptionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        db=sqlite3.connect(self.root/"weex_user_live_lifecycle.sqlite3")
        db.execute("CREATE TABLE trades_v1 (id TEXT,symbol TEXT,state TEXT,owned TEXT,plan TEXT)")
        db.execute("CREATE TABLE writes_v1 (trade_id TEXT,kind TEXT,response TEXT)")
        self.owned={"entryOrderId":"42","positionId":"123","quantity":"2","actualEntryCostUSDT":"100","actualEntryFeesUSDT":"0.1","tpRequest":{"triggerPrice":"52","triggerPriceType":"MARK_PRICE"}}
        self.plan={"entrySource":"automatic","entry":{"positionSide":"LONG"}}
        db.execute("INSERT INTO trades_v1 VALUES(?,?,?,?,?)",("t","LTCUSDT","REVIEW_REQUIRED",json.dumps(self.owned),json.dumps(self.plan)))
        db.execute("INSERT INTO writes_v1 VALUES(?,?,?)",("t","ENTRY",json.dumps({"success":True,"orderId":"42"})))
        db.commit();db.close()
        self.rows=([{"symbol":"LTCUSDT","id":123,"side":"LONG","size":"2","openValue":"100","openFee":"0.1"}],[],[{"symbol":"LTCUSDT","algoId":456,"orderType":"TAKE_PROFIT_MARKET","algoStatus":"UNTRIGGERED","positionSide":"LONG","side":"SELL","reduceOnly":True,"closePosition":True,"triggerPrice":"51","workingType":"CONTRACT_PRICE"}])
    def check(self,rows=None):
        from weex_lifecycle import now
        return verify(self.root,"t",rows if rows is not None else self.rows,now())
    def test_accept_manual_external(self):
        x=self.check()
        self.assertEqual(x["origin"],"MANUAL_EXTERNAL")
        self.assertTrue(x["notBotDispatched"])
    def test_reject_missing_tp(self):
        x=copy.deepcopy(self.rows);x[2].clear()
        with self.assertRaises(ValueError):self.check(x)
    def test_reject_duplicate_tp(self):
        x=copy.deepcopy(self.rows);x[2].append(copy.deepcopy(x[2][0]))
        with self.assertRaises(ValueError):self.check(x)
    def test_reject_wrong_position(self):
        x=copy.deepcopy(self.rows);x[0][0]["id"]=999
        with self.assertRaises(ValueError):self.check(x)
    def test_reject_partial_position(self):
        x=copy.deepcopy(self.rows);x[0][0]["size"]="1"
        with self.assertRaises(ValueError):self.check(x)
    def test_reject_non_reduce_only(self):
        x=copy.deepcopy(self.rows);x[2][0]["reduceOnly"]=False
        with self.assertRaises(ValueError):self.check(x)
    def test_reject_wrong_side(self):
        x=copy.deepcopy(self.rows);x[2][0]["side"]="BUY"
        with self.assertRaises(ValueError):self.check(x)
    def test_reject_stale_snapshot(self):
        from weex_lifecycle import now
        with self.assertRaisesRegex(ValueError,"STALE_ACCOUNT_SNAPSHOT"):
            verify(self.root,"t",self.rows,now()-60000)
    def test_reject_previous_bot_tp_dispatch(self):
        with __import__('contextlib').closing(sqlite3.connect(self.root/"weex_user_live_lifecycle.sqlite3")) as db:
            db.execute("INSERT INTO writes_v1 VALUES(?,?,?)",("t","TP","{}"))
            db.commit()
        with self.assertRaisesRegex(ValueError,"BOT_TP_DISPATCH_ALREADY_RECORDED"):self.check()
    def test_reject_other_regular_order(self):
        x=copy.deepcopy(self.rows);x[1].append({"symbol":"LTCUSDT"})
        with self.assertRaisesRegex(ValueError,"OTHER_REGULAR_ORDERS"):self.check(x)
    def test_reject_unprofitable_tp(self):
        x=copy.deepcopy(self.rows);x[2][0]["triggerPrice"]="49"
        with self.assertRaisesRegex(ValueError,"TP_NOT_PROFITABLE"):self.check(x)
if __name__=="__main__":unittest.main()
