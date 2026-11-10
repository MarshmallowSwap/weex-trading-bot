"""Regression against authenticated API-SIM snapshots, strictly offline."""
import unittest,json
from pathlib import Path
from weex_pilot_attached_stop_evidence import protected_entry
from weex_pilot_exit_stop_lifecycle import assess
ROOT=Path(__file__).resolve().parent
class ActualSimProtection(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.trial=json.loads((ROOT/'weex_sim_eth_trial_one_shot.json').read_text())
  cls.readback=json.loads((ROOT/'weex_sim_eth_trial_readback_latest.json').read_text())
  cls.final=json.loads((ROOT/'weex_sim_eth_trial_final_audit.json').read_text())
 @classmethod
 def inputs(cls):
  proposal={'entry':{'newClientOrderId':cls.trial['clientOrderId'],
     'SlWorkingType':'MARK_PRICE','slTriggerPrice':cls.trial['stopPrice']}}
  return proposal,cls.readback['get_capi_v3_order'],cls.readback['get_capi_v3_openAlgoOrders']
 def test_attached_sim_stop_corresponds_to_parent(self):
  p,o,st=self.inputs()
  r=protected_entry(p,o,st,'LONG','0.002')
  self.assertTrue(r['verified'],r)
 def test_wrong_link_rejected(self):
  p,o,st=self.inputs();st=[{**st[0],'actualOrderId':'not_original'}]
  self.assertFalse(protected_entry(p,o,st,'LONG','0.002')['verified'])
 def test_wrong_client_algo_rejected(self):
  p,o,st=self.inputs();st=[{**st[0],'clientAlgoId':'manual_stop'}]
  self.assertFalse(protected_entry(p,o,st,'LONG','0.002')['verified'])
 def test_wrong_quantity_rejected(self):
  p,o,st=self.inputs();st=[{**st[0],'quantity':'0.003'}]
  self.assertFalse(protected_entry(p,o,st,'LONG','0.002')['verified'])
 def test_wrong_trigger_rejected(self):
  p,o,st=self.inputs();st=[{**st[0],'triggerPrice':'2000'}]
  self.assertFalse(protected_entry(p,o,st,'LONG','0.002')['verified'])
 def test_wrong_working_type_rejected(self):
  p,o,st=self.inputs();st=[{**st[0],'workingType':'CONTRACT_PRICE'}]
  self.assertFalse(protected_entry(p,o,st,'LONG','0.002')['verified'])
 def test_attached_stop_blocks_competing_close(self):
  p,o,st=self.inputs()
  position=self.readback['get_capi_v3_account_position_allPosition'][0]
  r=assess(positions=[position],regular=[],conditional=st,
    expected_position=position,expected_stop={'algoId':str(st[0]['algoId']),
    'triggerPrice':st[0]['triggerPrice']})
  self.assertFalse(r['readyToDispatchEmergency'])
  self.assertEqual(r['reason'],'STOP_ACTIVE_CANCEL_CONFIRMATION_REQUIRED_BEFORE_POSITION_CLOSE')
 def test_final_audit_flat_and_reduce_only_fill(self):
  self.assertTrue(self.final['accountFlatVerified'])
  self.assertTrue(self.final['closeFillVerified'])
  self.assertTrue(self.final['stopHistoricalTerminalProof'])
  self.assertEqual(self.final['productionMode'],'STOPPED')
if __name__=='__main__':unittest.main()
