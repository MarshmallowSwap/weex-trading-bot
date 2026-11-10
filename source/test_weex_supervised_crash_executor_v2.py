"""Offline safety verification; NO live exchange requests or orders."""
import copy,tempfile,unittest,json,sqlite3
from pathlib import Path
from unittest.mock import patch
from weex_supervised_crash_executor_v2 import (
 validate_scope,Blocked,reserve,fake_exchange_accepted,recover_no_retry,
 drill,CLIENT_ID,QUANTITY)
from test_weex_pretrade_regression import META

class SupervisedV2(unittest.TestCase):
 def setUp(self):
  self.cfg={'execution':{'enabled':False,'mode':'PRETRADE'},
       'risk':{'minimumLeverage':100,'stopLoss':{'enabled':False}}}
  self.meta={**META,'symbol':'ETHUSDT','maxLeverage':400,
             'minOrderSize':'0.001','quantityPrecision':3,'pricePrecision':2}
  self.tiers=[{'notionalFloor':0,'notionalCap':1000,'initialLeverage':400}]
  self.settings=[{'symbol':'ETHUSDT','marginType':'CROSSED','separatedType':'COMBINED','crossLeverage':'100'}]
  self.book={'symbol':'ETHUSDT','status':'OK','depthUnitVerified':True,
         'bestBid':'2119.90','bestAsk':'2120.00'}
  self.account={'complete':True,'flat':True,'recoveryClear':True,'noUnresolvedWrites':True}
 def go(self):
  return validate_scope(config=self.cfg,contract=self.meta,tiers=self.tiers,
         settings=self.settings,book=self.book,account=self.account)
 def must_block(self,reason):
  with self.assertRaisesRegex(Blocked,reason):self.go()
 def test_100x_scope_with_exchange_atomic_stop(self):
  x=self.go()
  self.assertEqual(x['leverage'],'100')
  self.assertEqual(x['quantity'],'0.001')
  self.assertEqual(x['notionalUSDT'],'2.12000')
  self.assertEqual(x['indicativeInitialMarginUSDT'],'0.02120')
  self.assertEqual(x['payload']['SlWorkingType'],'MARK_PRICE')
  self.assertEqual(x['payload']['slTriggerPrice'],'2113.64')
  self.assertEqual(x['ordersSent'],0)
  self.assertFalse(x['liveApproved'])
 def test_50x_account_rejected(self):
  self.settings[0]['crossLeverage']='50';self.must_block('ACCOUNT_CROSS_100X')
 def test_99x_tier_rejected(self):
  self.tiers[0]['initialLeverage']=99;self.must_block('PUBLIC_RISK_TIER')
 def test_contract_below_100_rejected(self):
  self.meta['maxLeverage']=99;self.must_block('CONTRACT_100X')
 def test_changed_min_qty_rejected(self):
  self.meta['minOrderSize']='0.01';self.must_block('MINIMUM_QUANTITY')
 def test_unverified_book_rejected(self):
  self.book['depthUnitVerified']=False;self.must_block('BOOK_NOT_VERIFIED')
 def test_too_large_notional_rejected(self):
  self.book.update(bestBid='6000',bestAsk='6001');self.must_block('MINIMUM_NOTIONAL_ABOVE_CAP')
 def test_unreconciled_account_rejected(self):
  self.account['noUnresolvedWrites']=False;self.must_block('ACCOUNT_RECOVERY')
 def test_live_bot_rejected(self):
  self.cfg['execution']['enabled']=True;self.must_block('PRODUCTION_MUST_REMAIN_DISARMED')
 def test_durable_record_prevents_second_entry(self):
  p={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
      'quantity':'0.001','newClientOrderId':CLIENT_ID,
      'slTriggerPrice':'2088.20','SlWorkingType':'MARK_PRICE'}
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/'drill.db'
   self.assertTrue(reserve(db,p))
   self.assertFalse(reserve(db,p))
   self.assertTrue(fake_exchange_accepted(db,p)['success'])
   with self.assertRaisesRegex(Blocked,'DUPLICATE_EXCHANGE_ORDER'):
    fake_exchange_accepted(db,p)
   recovered=recover_no_retry(db,p)
   self.assertTrue(recovered['attachedStopVerified'])
   self.assertTrue(recovered['exactOrderCloseVerified'])
   self.assertEqual(recovered['duplicateOrders'],0)
   self.assertFalse(reserve(db,p))
 def test_tampered_stop_blocks_recovery(self):
  p={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
      'quantity':'0.001','newClientOrderId':CLIENT_ID,
      'slTriggerPrice':'2088.20','SlWorkingType':'MARK_PRICE'}
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/'drill.db'
   reserve(db,p);fake_exchange_accepted(db,p)
   with __import__("contextlib").closing(sqlite3.connect(db)) as conn, conn:
    conn.execute('UPDATE exchange_order SET stop=?',('0',))
   with self.assertRaisesRegex(Blocked,'EXCHANGE_ORDER_OR_STOP_MISMATCH'):
    recover_no_retry(db,p)
 def test_real_process_crash_is_offline(self):
  r=drill()
  self.assertEqual(r['childExitCode'],79)
  self.assertEqual(r['fakeEntryOrders'],1)
  self.assertEqual(r['fakeCloseOrders'],1)
  self.assertEqual(r['productionOrderWrites'],0)
  self.assertEqual(r['networkRequests'],0)
  self.assertFalse(r['productionReleaseCertified'])

if __name__=='__main__':unittest.main()

