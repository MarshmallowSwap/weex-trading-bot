import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from weex_cross_1x_operator_telegram_20261109 import challenge,confirm,current_scope,AUTH,FILENAME
from weex_cross_1x_single_use_approval_20261109 import SingleUseApproval
from test_weex_cross_1x_emergency_readiness_20261109 import I,E,P,S
from telegram_live_control import handle
class Reader:
 def __init__(self,p=None,s=None):self.p=[P] if p is None else p;self.s=[S] if s is None else s
 def read(self,op,**q):
  if op=='get_capi_v3_order':return E
  if op=='get_capi_v3_account_symbolConfig':
   return [{'marginType':'CROSSED','crossLeverage':'1'}]
  raise AssertionError('UNEXPECTED_READ')
 def account(self):return self.p,[],self.s
class TelegramOperator(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
  (self.root/FILENAME).write_text(json.dumps({
   'intent':I,'entryOrderId':'101','stopAlgoId':'301','positionId':'201'}))
  self.reader=Reader()
  self.guard1=patch('live_control.state',return_value={'mode':'STOPPED'});self.guard1.start();self.addCleanup(self.guard1.stop)
  self.guard2=patch('live_control.build_errors',return_value=[]);self.guard2.start();self.addCleanup(self.guard2.stop)
 def test_challenge_confirmation_consumed_once(self):
  q=challenge(self.root,'500','400',reader=self.reader)
  self.assertTrue(confirm(self.root,q['nonce'],'500','400',reader=self.reader))
  self.assertFalse(confirm(self.root,q['nonce'],'500','400',reader=self.reader))
  self.assertTrue(SingleUseApproval(self.root/AUTH)(q['scope']))
  self.assertFalse(SingleUseApproval(self.root/AUTH)(q['scope']))
 def test_wrong_user_rejected(self):
  q=challenge(self.root,'500','400',reader=self.reader)
  self.assertFalse(confirm(self.root,q['nonce'],'999','400',reader=self.reader))
  self.assertTrue(confirm(self.root,q['nonce'],'500','400',reader=self.reader))
 def test_wrong_chat_rejected(self):
  q=challenge(self.root,'500','400',reader=self.reader)
  self.assertFalse(confirm(self.root,q['nonce'],'500','401',reader=self.reader))
 def test_changed_position_rejected(self):
  q=challenge(self.root,'500','400',reader=self.reader)
  self.assertFalse(confirm(self.root,q['nonce'],'500','400',reader=Reader(p=[])))
 def test_no_pilot_file_rejected(self):
  (self.root/FILENAME).unlink()
  with self.assertRaises(PermissionError):challenge(self.root,'500','400',reader=self.reader)
 def test_stop_lost_rejected(self):
  with self.assertRaises(PermissionError):challenge(self.root,'500','400',reader=Reader(s=[]))
 def test_running_bot_rejected(self):
  with patch('live_control.state',return_value={'mode':'RUNNING'}):
   with self.assertRaises(PermissionError):challenge(self.root,'500','400',reader=self.reader)
 def test_second_challenge_same_pilot_rejected(self):
  challenge(self.root,'500','400',reader=self.reader)
  with self.assertRaises(PermissionError):challenge(self.root,'500','400',reader=self.reader)
 def test_expired_nonce_rejected(self):
  q=challenge(self.root,'500','400',reader=self.reader,now=time.time()-300)
  self.assertFalse(confirm(self.root,q['nonce'],'500','400',reader=self.reader))
 def test_handler_unauthorized_chat_ignored(self):
  cfg={'telegram_chat_id':'400','telegram_user_id':'500'}
  u={'message':{'chat':{'id':'403'},'from':{'id':'500'},
    'date':int(time.time()),'text':'/crossclose'}}
  result=handle(u,cfg,self.root)
  self.assertIsNone(result['reply'])
 def test_handler_without_position_refuses(self):
  cfg={'telegram_chat_id':'400','telegram_user_id':'500'}
  (self.root/FILENAME).unlink()
  u={'message':{'chat':{'id':'400'},'from':{'id':'500'},
    'date':int(time.time()),'text':'/crossclose'}}
  result=handle(u,cfg,self.root)
  self.assertIn('NO_PENDING_CROSS_PILOT',result['reply']['text'])
 def test_handler_rejects_stale_message(self):
  cfg={'telegram_chat_id':'400','telegram_user_id':'500'}
  u={'message':{'chat':{'id':'400'},'from':{'id':'500'},
    'date':int(time.time())-500,'text':'/crossclose'}}
  r=handle(u,cfg,self.root);self.assertIn('scaduta',r['reply']['text'])
if __name__=='__main__':unittest.main()
