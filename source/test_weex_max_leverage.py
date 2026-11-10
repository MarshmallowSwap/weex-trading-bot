import copy,tempfile,unittest,json
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch
from weex_max_leverage import select
from test_weex_pretrade_regression import META,MARKET,ACCOUNT,CFG
from test_weex_lifecycle import Exchange,PLAN,CFG as LIVE_CFG
from weex_lifecycle import Lifecycle
from weex_simple_bot import preview,run
from weex_account_setup_audit import assess

TIERS=[{'notionalFloor':'0','notionalCap':'550','initialLeverage':125},
       {'notionalFloor':'550','notionalCap':'30000','initialLeverage':100}]

class MaximumLeverageTests(unittest.TestCase):
    def choose(self,**kwargs):
        args=dict(metadata={**META,'maxLeverage':125},brackets=TIERS,margin_usdt=5,reference_price=1)
        args.update(kwargs);return select(**args)
    def test_max_leverage_retained_by_reducing_quantity_below_tier_cap(self):
        result=self.choose()
        self.assertEqual(result['leverage'],'125')
        self.assertLess(Decimal(result['notionalUSDT']),550)
        self.assertLessEqual(Decimal(result['initialMarginUSDT']),5)
        self.assertTrue(result['quantityCappedByTier'])
    def test_no_tier_reduction_when_advertised_max_fits(self):
        result=self.choose(metadata=META,brackets=[{'notionalFloor':0,'notionalCap':100000,'initialLeverage':400}],reference_price=2400)
        self.assertEqual(result['leverage'],'400');self.assertFalse(result['quantityCappedByTier'])
    def test_higher_tier_leverage_not_account_default_is_used(self):
        result=self.choose(metadata={**META,'maxLeverage':200})
        self.assertEqual(result['leverage'],'125')
    def test_floor_100_cannot_be_lowered_by_configuration(self):
        with self.assertRaisesRegex(ValueError,'100_OR_HIGHER'):
            self.choose(metadata={**META,'maxLeverage':99},minimum=1)
    def test_minimum_quantity_can_require_lower_valid_tier_but_never_below_100(self):
        meta={**META,'maxLeverage':125,'minOrderSize':'600'}
        with self.assertRaises(ValueError):self.choose(metadata=meta)
        result=self.choose(metadata=meta,margin_usdt=10)
        self.assertEqual(result['leverage'],'100')
    def test_negative_quantity_precision_and_exact_cap(self):
        result=self.choose(metadata={**META,'maxLeverage':125,'quantityPrecision':-2,'minOrderSize':'100'})
        self.assertEqual(result['quantity'],'500');self.assertEqual(result['leverage'],'125')
    def test_missing_overlapping_or_nonfinite_tiers_rejected(self):
        for tiers in ([],[TIERS[0],TIERS[0]], [{'notionalFloor':0,'notionalCap':'NaN','initialLeverage':125}]):
            with self.subTest(tiers=tiers),self.assertRaises(ValueError):self.choose(brackets=tiers)
    def test_preview_and_audit_use_same_maximum_and_capped_quantity(self):
        metadata={**META,'maxLeverage':125,'contractType':'PERPETUAL'}
        market={**MARKET,'realOrderBook':{**MARKET['realOrderBook'],'bestAsk':'1','bestBid':'0.999'}}
        plan=preview(market,metadata,ACCOUNT,CFG,brackets=TIERS)
        audit=assess([metadata],{'ETHUSDT'},[ACCOUNT],[{'symbol':'ETHUSDT','brackets':TIERS}],5,prices={'ETHUSDT':'1'})[0]
        self.assertEqual(plan['requestedLeverage'],audit['requestedLeverage'])
        self.assertEqual(plan['sizing']['quantity'],audit['sizing']['quantity'])
        self.assertTrue(plan['publicRiskTierVerified']);self.assertTrue(audit['publicTierAllowsTarget'])
    def test_executor_rejects_prepared_plan_below_100(self):
        with tempfile.TemporaryDirectory() as folder:
            engine=Lifecycle(Path(folder)/'test.db',Exchange(),lambda:LIVE_CFG)
            plan=copy.deepcopy(PLAN);plan['requestedLeverage']='99'
            with self.assertRaisesRegex(ValueError,'LEVERAGE_BELOW_100'):engine.prepare('below',plan)
    def test_live_guard_rejects_plan_when_fresh_maximum_changed(self):
        import test_weex_lifecycle as fixtures
        with tempfile.TemporaryDirectory() as folder:
            engine=Lifecycle(Path(folder)/'test.db',Exchange(),lambda:LIVE_CFG)
            item=engine.prepare('old',PLAN)
            context={'maximumPermittedLeverage':'125'}
            with self.assertRaisesRegex(ValueError,'MAXIMUM_LEVERAGE_CHANGED'):engine.guard(item,context)
    def test_pilot_entrypoint_disabled_by_always_minimum_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'weex_ai_risk_config.json').write_text(json.dumps(CFG))
            with patch('weex_simple_bot.R',root),patch('weex_simple_bot.make_client') as client:
                with self.assertRaisesRegex(ValueError,'PILOT_1X_DISABLED'):run('ETHUSDT',pilot=True)
                client.assert_not_called()

if __name__=='__main__':unittest.main()
