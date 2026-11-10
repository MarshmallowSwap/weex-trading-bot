"""End-to-end: mock lifecycle journal -> WEEX-style readback -> Telegram PNG."""
import copy,tempfile,unittest
from pathlib import Path
from weex_lifecycle import Lifecycle,now
from test_weex_lifecycle import Exchange,CFG,PLAN
from weex_position_reports import bot_tp_previews,open_rows
from weex_position_cards import render
class BotTPCardIntegration(unittest.TestCase):
 def test_real_lifecycle_fixture_generates_and_renders_net_preview(self):
  with tempfile.TemporaryDirectory() as dirname:
   root=Path(dirname);cfg=copy.deepcopy(CFG)
   cfg['strategySettings'].update(targetNetProfitUSDT=20,tpAccountingMode='GROSS_BEFORE_COSTS')
   plan=copy.deepcopy(PLAN)
   plan.update(targetNetProfitUSDT='20',tpAccountingMode='GROSS_BEFORE_COSTS')
   fake=Exchange()
   engine=Lifecycle(root/'weex_user_live_lifecycle.sqlite3',fake,lambda:cfg)
   item=engine.prepare('telegram-gross-net-integrated',plan)
   def context(symbol):
    return {'observedAtMs':now(),'complete':True,'apiEnabled':True,'accountCanTrade':True,
     'hedgeMode':True,'depthUnitVerified':True,'liquidityPassed':True,
     'marketSignal':'LONG','riskTierVerified':True,'availableBalance':'100',
     'positions':[],'openOrders':[],'conditionalOrders':[],
     'symbolConfig':{'symbol':symbol,'marginType':fake.margin,'crossLeverage':fake.leverage},
     'referencePrice':'2500','exitFeeRate':'.0008','maximumPermittedLeverage':'100'}
   self.assertEqual(engine.advance(item['id'],context)['state'],'TP_PENDING')
   self.assertEqual(engine.reconcile(item['id'])['state'],'PROTECTED')
   observed={**fake.positions[0],'asset':'USDT','leverage':'100',
             'openValue':'50.00','openFee':'0.04','unrealizePnl':'0','marginType':'CROSSED'}
   previews=bot_tp_previews(root)
   self.assertEqual(len(previews),1)
   rows=open_rows([observed],fake.algos,tp_previews=previews)
   self.assertEqual(len(rows),1)
   self.assertEqual(rows[0]['tpGrossTargetUSDT'],'20')
   self.assertLess(float(rows[0]['tpNetEstimatedUSDT']),20)
   report={'kind':'open','rows':rows,'observedAtMs':10000000,
           'windowEndMs':10000000,'stale':False,'error':None}
   self.assertTrue(render(report)[0].startswith(bytes([137,80,78,71])))
   changed={**observed,'openValue':'50.01'}
   self.assertNotIn('tpNetEstimatedUSDT',open_rows([changed],fake.algos,tp_previews=previews)[0])
   self.assertEqual(len(fake.calls),2)
if __name__=='__main__':unittest.main()
