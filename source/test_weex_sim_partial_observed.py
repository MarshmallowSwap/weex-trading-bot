"""WEEX simulation-observed 50% partial close remains original TP/SL qty.
All outcomes must remain blocked until manual/exchange-verified reconciliation.
"""
import unittest,tempfile
from pathlib import Path
from weex_sim_conditional_recovery import register,observe

class RealDemoShapeTests(unittest.TestCase):
 def test_simulated_020_to_010_stale_tp_sl(self):
  with tempfile.TemporaryDirectory() as td:
   db=str(Path(td)/'partial.sqlite')
   register(db,'sim-partial',position_id=8831,symbol='BTCUSDT',side='LONG',
      entry_quantity='0.0002',tp_client_id='tp-sim',sl_client_id='sl-sim',
      entry_cost='20',entry_fees='.01')
   orders=[
      dict(clientAlgoId='tp-sim',symbol='BTCUSDT',positionSide='LONG',
           side='SELL',reduceOnly=True,quantity='0.0002',
           orderType='TAKE_PROFIT_LIMIT',price='103000',algoStatus='UNTRIGGERED'),
      dict(clientAlgoId='sl-sim',symbol='BTCUSDT',positionSide='LONG',
           side='SELL',reduceOnly=True,quantity='0.0002',
           orderType='STOP_LOSS_MARKET',price='0',algoStatus='UNTRIGGERED')]
   fill=[dict(id='fill1',positionId=8831,symbol='BTCUSDT',positionSide='LONG',
              side='SELL',commissionAsset='USDT',qty='0.0001',
              price='100000',commission='.005')]
   out=observe(db,'sim-partial',
       positions=[dict(id=8831,symbol='BTCUSDT',side='LONG',size='0.0001')],
       algos=orders,regular_orders=[],exit_fills=fill,source_confirmed=True)
   self.assertEqual(out['state'],'PARTIAL_RECONCILIATION_REQUIRED')
   self.assertTrue(out['evidence']['protectionOversized'])
   self.assertEqual(out['evidence']['riskReason'],'STALE_TP_SL_QUANTITY_AFTER_PARTIAL')
   self.assertFalse(out['actionsAllowed'])
   self.assertFalse(out['canRetry'])
   self.assertFalse(out['stopLossCoverageCertified'])

 def test_fully_closed_does_not_flag_oversized_protection(self):
  with tempfile.TemporaryDirectory() as td:
   db=str(Path(td)/'done.sqlite')
   register(db,'sim-close',position_id=8831,symbol='BTCUSDT',side='LONG',
      entry_quantity='0.0002',tp_client_id='tp-sim',sl_client_id='sl-sim',
      entry_cost='20',entry_fees='.01')
   fill=[dict(id='fill1',positionId=8831,symbol='BTCUSDT',positionSide='LONG',
              side='SELL',commissionAsset='USDT',qty='0.0002',
              price='100000',commission='.01')]
   out=observe(db,'sim-close',positions=[],algos=[],regular_orders=[],
               exit_fills=fill,source_confirmed=True)
   self.assertEqual(out['state'],'CLOSED_READBACK_NO_OCO_PROOF')
   self.assertFalse(out['evidence']['protectionOversized'])
if __name__=='__main__':unittest.main()
