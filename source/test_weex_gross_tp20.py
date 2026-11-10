"""Gross 20 USDT TP: pricing and lifecycle regression, entirely in memory."""
import copy,tempfile,unittest
from pathlib import Path
from decimal import Decimal
from weex_tp_pnl_preview import gross_preview
from weex_lifecycle import Lifecycle,now
from test_weex_lifecycle import Exchange,CFG,PLAN

class GrossTP(unittest.TestCase):
 def test_long_20_gross(self):
  x=gross_preview(side='LONG',quantity='2',entry_cost_usdt='200',
   entry_fees_usdt='.16',exit_fee_rate='.0008',target_gross_usdt='20',
   price_tick='.01',estimated_slippage_rate='.001')
  self.assertEqual(Decimal(x['triggerPrice']),Decimal('110.00'))
  self.assertEqual(Decimal(x['estimatedGrossAtTriggerUSDT']),Decimal('20.00'))
  self.assertLess(Decimal(x['estimatedNetAfterFeesSlippageUSDT']),Decimal('20'))
  self.assertFalse(x['dispatchAllowed'])
 def test_short_20_gross(self):
  x=gross_preview(side='SHORT',quantity='2',entry_cost_usdt='200',
   entry_fees_usdt='.16',exit_fee_rate='.0008',target_gross_usdt='20',
   price_tick='.01')
  self.assertEqual(Decimal(x['triggerPrice']),Decimal('90.00'))
  self.assertEqual(Decimal(x['estimatedGrossAtTriggerUSDT']),Decimal('20.00'))
 def test_fractional_rounding(self):
  for side in ('LONG','SHORT'):
   x=gross_preview(side=side,quantity='3',entry_cost_usdt='300',
    entry_fees_usdt='.1',exit_fee_rate='.001',
    target_gross_usdt='20',price_tick='.05')
   self.assertGreaterEqual(Decimal(x['estimatedGrossAtTriggerUSDT']),20)
 def test_short_unreachable(self):
  with self.assertRaisesRegex(ValueError,'GROSS_TP_UNREACHABLE'):
   gross_preview(side='SHORT',quantity='1',entry_cost_usdt='10',
    entry_fees_usdt='.01',exit_fee_rate='.001',
    target_gross_usdt='20',price_tick='.01')
 def test_net_and_gross_differ(self):
  from weex_tp_pnl_preview import preview
  gross=gross_preview(side='LONG',quantity='2',entry_cost_usdt='200',
    entry_fees_usdt='.16',exit_fee_rate='.0008',
    target_gross_usdt='20',price_tick='.01')
  net=preview(side='LONG',quantity='2',entry_cost_usdt='200',
    entry_fees_usdt='.16',exit_fee_rate='.0008',
    target_net_usdt='20',price_tick='.01')
  self.assertLess(Decimal(gross['triggerPrice']),Decimal(net['triggerPrice']))
 def test_gross_lifecycle_entry_and_tp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
  cfg=copy.deepcopy(CFG)
  cfg['strategySettings'].update(targetNetProfitUSDT=20,tpAccountingMode='GROSS_BEFORE_COSTS')
  plan=copy.deepcopy(PLAN)
  plan.update(targetNetProfitUSDT='20',tpAccountingMode='GROSS_BEFORE_COSTS')
  ex=Exchange()
  engine=Lifecycle(Path(temp.name)/'db.sqlite3',ex,lambda:cfg)
  item=engine.prepare('gross-cycle',plan)
  def context(symbol):
   return {'observedAtMs':now(),'complete':True,'apiEnabled':True,
     'accountCanTrade':True,'hedgeMode':True,'depthUnitVerified':True,
     'liquidityPassed':True,'marketSignal':'LONG','riskTierVerified':True,
     'availableBalance':'100','positions':[],'openOrders':[],'conditionalOrders':[],
     'symbolConfig':{'symbol':symbol,'marginType':ex.margin,'crossLeverage':ex.leverage},
     'referencePrice':'2500','exitFeeRate':'.0008','maximumPermittedLeverage':'100'}
  out=engine.advance(item['id'],context)
  self.assertEqual(out['state'],'TP_PENDING')
  owned=engine.get(item['id'])['owned']
  self.assertEqual(owned['tpPnlPreview']['mode'],'PNL_GROSS_BEFORE_COSTS_USDT')
  self.assertGreaterEqual(Decimal(owned['tpPnlPreview']['estimatedGrossAtTriggerUSDT']),20)
  self.assertEqual(engine.reconcile(item['id'])['state'],'PROTECTED')
  self.assertEqual([w[0] for w in ex.calls],
    ['post_capi_v3_order','post_capi_v3_placeTpSlOrder'])
  self.assertEqual(engine.reconcile(item['id'])['state'],'PROTECTED')
  self.assertEqual(len(ex.calls),2)
 def test_unsupported_accounting_blocks(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
  cfg=copy.deepcopy(CFG)
  cfg['strategySettings'].update(targetNetProfitUSDT=20,tpAccountingMode='GROSS_BEFORE_COSTS')
  plan=copy.deepcopy(PLAN)
  plan.update(targetNetProfitUSDT='20',tpAccountingMode='INVALID')
  engine=Lifecycle(Path(temp.name)/'db.sqlite3',Exchange(),lambda:cfg)
  item=engine.prepare('invalid-cycle',plan)
  self.assertEqual(item['state'],'PREPARED')

if __name__=='__main__':unittest.main()
