"""Offline tests for real worker crash proof gate. No network or orders."""
import hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from weex_real_worker_crash_evidence_gate import certify,SCOPE,HOST,NAME

CID='wxentry_0123456789abcdef01234567'
class Fixture:
 def __init__(self,root):
  self.root=root
  manifest={'sha256':{}}
  for f in ('weex_live_worker.py','weex_lifecycle.py'):
   data=('tested '+f).encode()
   (root/f).write_bytes(data)
   manifest['sha256'][f]=hashlib.sha256(data).hexdigest()
  (root/'live_release_manifest.json').write_text(json.dumps(manifest))
  self.entry={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
              'quantity':'0.002','newClientOrderId':CID}
  db=sqlite3.connect(root/'weex_user_live_lifecycle.sqlite3')
  db.execute('CREATE TABLE trades_v1(id TEXT,plan TEXT)')
  db.execute('CREATE TABLE writes_v1(trade_id TEXT,kind TEXT,operation TEXT,payload TEXT,state TEXT,response TEXT)')
  db.execute('INSERT INTO trades_v1 VALUES (?,?)',(CID,json.dumps({'entry':self.entry})))
  db.execute('INSERT INTO writes_v1 VALUES (?,?,?,?,?,?)',
    (CID,'ENTRY','post_capi_v3_order',json.dumps(self.entry),'UNKNOWN',None))
  db.commit();db.close()
  self.report={'scope':SCOPE,'host':HOST,'worker':'weex_live_worker.py',
    'lifecycle':'weex_lifecycle.py','childExitCode':79,
    'phase':'ENTRY_ACK_RETURNED_BEFORE_SQLITE_ACK','networkEntryDispatches':1,
    'entryRetries':0,'restartNewProcess':True,'stopActiveBeforeClose':True,
    'supervisedExit':True,'independentAudit':True,'exchangeWritesDuringAudit':0,
    'workerSha256':manifest['sha256']['weex_live_worker.py'],
    'lifecycleSha256':manifest['sha256']['weex_lifecycle.py'],
    'tradeId':CID,'clientOrderId':CID,'entryOrderId':'101','closeOrderId':'102',
    'stopAlgoId':'103','symbol':'ETHUSDT','quantity':'0.002'}
  self.opened={'orderId':'101','clientOrderId':CID,'status':'FILLED','symbol':'ETHUSDT',
    'positionSide':'LONG','side':'BUY','executedQty':'0.002'}
  self.closed={'orderId':'102','status':'FILLED','reduceOnly':True,
    'symbol':'ETHUSDT','positionSide':'LONG','side':'SELL','executedQty':'0.002'}
  self.entryfills=[{'id':'1','orderId':'101','qty':'0.002','side':'BUY'}]
  self.closefills=[{'id':'2','orderId':'102','qty':'0.002','side':'SELL'}]
  self.stop={'algoId':'103','algoStatus':'CANCELED','symbol':'ETHUSDT',
    'positionSide':'LONG','side':'SELL','orderType':'STOP_MARKET','reduceOnly':True,
    'clientAlgoId':CID+'sl','actualOrderId':'101','quantity':'0.002'}
  self.reader=Mock()
  self.reader.read.side_effect=lambda op,**q:{
   ('get_capi_v3_order','101') :self.opened,
   ('get_capi_v3_order','102') :self.closed,
   ('get_capi_v3_userTrades','101') :self.entryfills,
   ('get_capi_v3_userTrades','102') :self.closefills,
   ('get_capi_v3_allAlgoOrders',None):{'orders':[self.stop]}
  }[(op,str(q['orderId']) if 'orderId' in q else None)]
  self.reader.account.return_value=([],[],[])
 def write(self):
  (self.root/NAME).write_text(json.dumps(self.report))

class EvidenceGateTests(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
  self.f=Fixture(Path(temp.name))
 def go(self):
  self.f.write()
  return certify(self.f.root,self.f.reader)
 def test_absent_fails(self):
  result=certify(self.f.root,self.f.reader)
  self.assertFalse(result['certified']);self.f.reader.read.assert_not_called()
 def test_valid_provenance_and_exchange_pass(self):
  self.assertTrue(self.go()['certified'])
 def test_demo_scope_fails_without_exchange_reads(self):
  self.f.report['scope']='WEEX_DEMO_CRASH'
  self.assertFalse(self.go()['certified']);self.f.reader.read.assert_not_called()
 def test_crash_during_get_not_accepted(self):
  self.f.report['phase']='READ_ONLY_CRASH'
  self.assertFalse(self.go()['certified']);self.f.reader.read.assert_not_called()
 def test_worker_code_hash_mismatch_fails(self):
  self.f.report['workerSha256']='invalid'
  self.assertFalse(self.go()['certified']);self.f.reader.read.assert_not_called()
 def test_nonzero_retries_fail(self):
  self.f.report['entryRetries']=1
  self.assertFalse(self.go()['certified'])
 def test_stop_not_linked_to_entry_fails(self):
  self.f.stop['actualOrderId']='777'
  self.assertFalse(self.go()['certified'])
 def test_unprotected_stop_fails(self):
  self.f.stop['reduceOnly']=False
  self.assertFalse(self.go()['certified'])
 def test_unverified_reduce_only_close_fails(self):
  self.f.closed['reduceOnly']=False
  self.assertFalse(self.go()['certified'])
 def test_partial_execution_fails(self):
  self.f.entryfills[0]['qty']='0.001'
  self.assertFalse(self.go()['certified'])
 def test_account_not_flat_fails(self):
  self.f.reader.account.return_value=([{'id':1,'symbol':'ETHUSDT'}],[],[])
  self.assertFalse(self.go()['certified'])
 def test_foreign_manual_position_and_tp_do_not_mask_verified_eth_close(self):
  self.f.reader.account.return_value=(
   [{'id':'901','symbol':'AINUSDT','side':'SHORT','size':'13200'}],[],
   [{'algoId':'902','symbol':'AINUSDT','side':'BUY','positionSide':'SHORT',
     'reduceOnly':True,'orderType':'TAKE_PROFIT_MARKET'}])
  self.assertTrue(self.go()['certified'])
 def test_foreign_symbol_does_not_mask_dangling_target_order(self):
  self.f.reader.account.return_value=(
   [{'id':'901','symbol':'AINUSDT','side':'SHORT'}],
   [{'symbol':'ETHUSDT','orderId':'999'}],[])
  self.assertFalse(self.go()['certified'])
 def test_no_actual_journal_fails(self):
  db=sqlite3.connect(self.f.root/'weex_user_live_lifecycle.sqlite3')
  db.execute("UPDATE writes_v1 SET state='RESPONSE_RECEIVED'");db.commit();db.close()
  self.assertFalse(self.go()['certified']);self.f.reader.read.assert_not_called()

if __name__=='__main__':unittest.main()
