"""Offline tests for fee/funding aware remaining-position TP."""
import unittest
from decimal import Decimal as D
from weex_tp_net_funding_guard import build
BASE={'side':'LONG','remaining_qty':'2','remaining_entry_value':'200',
      'remaining_entry_fees':'.16','remaining_funding_paid':'.30',
      'realized_net_before_funding':'0','realized_funding_paid':'0',
      'exit_fee_rate':'.0008','limit_tick':'.01','target_net_usdt':'15',
      'funding_evidence_verified':True,'entry_evidence_verified':True,
      'exit_fee_evidence_verified':True,'partial_exit_evidence_verified':True}
def calc(**overrides):
 return build(**{**BASE,**overrides})
class NetFunding(unittest.TestCase):
 def test_long_net_at_limit(self):
  x=calc()
  self.assertEqual(x['state'],'FUNDING_AWARE_TP_PREVIEW_ONLY')
  self.assertGreaterEqual(D(x['theoreticalTotalNetAtLimitUSDT']),D('15'))
  self.assertFalse(x['canSubmit'])
 def test_funding_paid_increases_long_target(self):
  a=calc(remaining_funding_paid='0')
  b=calc(remaining_funding_paid='2')
  self.assertGreater(D(b['tpLimitPrice']),D(a['tpLimitPrice']))
 def test_funding_credit_lowers_long_target(self):
  a=calc(remaining_funding_paid='0')
  b=calc(remaining_funding_paid='-1')
  self.assertLess(D(b['tpLimitPrice']),D(a['tpLimitPrice']))
 def test_short_funding_paid_decreases_target(self):
  kwargs={'side':'SHORT'}
  a=calc(**kwargs,remaining_funding_paid='0')
  b=calc(**kwargs,remaining_funding_paid='1')
  self.assertLess(D(b['tpLimitPrice']),D(a['tpLimitPrice']))
 def test_missing_funding_proof_blocks(self):
  self.assertEqual(calc(funding_evidence_verified=False)['state'],'BLOCKED')
 def test_missing_fees_blocks(self):
  self.assertEqual(calc(exit_fee_evidence_verified=False)['state'],'BLOCKED')
 def test_missing_partial_fill_proof_blocks(self):
  self.assertEqual(calc(partial_exit_evidence_verified=False)['state'],'BLOCKED')
 def test_partial_profit_reduces_remaining_target(self):
  x=calc(remaining_qty='1',remaining_entry_value='100',
         remaining_entry_fees='.08',remaining_funding_paid='.1',
         realized_net_before_funding='6',realized_funding_paid='.5')
  self.assertEqual(x['previousRealizedNetUSDT'],'5.5')
  self.assertEqual(x['remainingTargetUSDT'],'9.5')
  self.assertFalse(x['canSubmit'])
 def test_partial_loss_increases_remaining_target(self):
  x=calc(realized_net_before_funding='-3')
  self.assertEqual(x['remainingTargetUSDT'],'18')
 def test_unreachable_short_target_blocks(self):
  x=calc(side='SHORT',remaining_qty='1',remaining_entry_value='2',
       remaining_entry_fees='0',remaining_funding_paid='0',
       target_net_usdt='15')
  self.assertEqual(x['reason'],'TARGET_PRICE_NOT_REACHABLE')
 def test_tick_rounding_does_not_undershoot(self):
  x=calc(limit_tick='1')
  self.assertGreaterEqual(D(x['theoreticalTotalNetAtLimitUSDT']),D('15'))
 def test_negative_fee_blocks(self):
  self.assertEqual(calc(remaining_entry_fees='-1')['state'],'BLOCKED')
 def test_nan_blocks(self):
  self.assertEqual(calc(remaining_qty='NaN')['state'],'BLOCKED')
 def test_slippage_guard_more_conservative(self):
  a=calc(expected_exit_slippage_rate='0')
  b=calc(expected_exit_slippage_rate='.005')
  self.assertGreater(D(b['tpLimitPrice']),D(a['tpLimitPrice']))
 def test_15_usdt_not_a_guaranteed_fill(self):
  x=calc()
  self.assertFalse(x['orderExecutionGuaranteed'])
  self.assertFalse(x['stopLossCertified'])
  self.assertFalse(x['ocoCertified'])
if __name__=='__main__':unittest.main()
