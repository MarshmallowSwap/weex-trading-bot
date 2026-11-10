import copy,unittest
from datetime import datetime,timezone,timedelta
from weex_simulation_domain import SIM,validate_contract
from weex_simulation_depth import assess,verify_simulation_units
from weex_depth_evidence import fingerprint

class Tests(unittest.TestCase):
    def setUp(self):
        self.at=datetime.now(timezone.utc)
        self.meta={'symbol':'BTCUSDT','baseAsset':'BTC','quoteAsset':'USDT','marginAsset':'USDT',
          'contractType':'PERPETUAL','quantityPrecision':4,'contractVal':'0.0001','forwardContractFlag':False}
        self.book={'bids':[['80000','0.1234']],'asks':[['80001','0.1234']]}
        self.evidence={'version':1,'sourceHost':SIM,'checkedAt':self.at.isoformat(),'symbols':{'BTCUSDT':{
          'metadata':fingerprint(self.meta),'method':'LOT_GRID_ELIMINATES_CONTRACT_COUNTS','restEvidence':{
           'rounds':3,'depthUpdateIds':[1,2,3],'levels':1000,'uniqueTrades':100,'tradeQuoteErrors':0,
           'rawQuantityStepViolations':0,'contractInterpretationStepViolations':900}}}}
    def check(self,**kwargs):
        return verify_simulation_units('BTCUSDT',kwargs.get('metadata',self.meta),kwargs.get('book',self.book),
           kwargs.get('evidence',self.evidence),source_host=kwargs.get('source_host',SIM),at=kwargs.get('at',self.at))[0]
    def test_scoped_evidence_matches(self):self.assertTrue(self.check())
    def test_production_evidence_rejected(self):
        self.evidence['sourceHost']='https://api-contract.weex.com'
        self.assertFalse(self.check())
    def test_production_book_rejected(self):self.assertFalse(self.check(source_host='https://api-contract.weex.com'))
    def test_expired_or_future_evidence(self):
        self.assertFalse(self.check(at=self.at+timedelta(hours=25)))
        self.assertFalse(self.check(at=self.at-timedelta(seconds=1)))
    def test_missing_evidence(self):self.assertFalse(self.check(evidence={}))
    def test_metadata_change(self):self.assertFalse(self.check(metadata=dict(self.meta,quantityPrecision=3)))
    def test_new_book_grid_break(self):
        self.book['bids'][0][1]='0.00001'
        self.assertFalse(self.check())
    def test_independent_updates_required(self):
        self.evidence['symbols']['BTCUSDT']['restEvidence']['depthUpdateIds']=[1,1,2]
        self.assertFalse(self.check())
    def test_units_do_not_override_contract_flag(self):
        result=assess('BTCUSDT',self.meta,self.book,self.evidence,source_host=SIM,at=self.at)
        self.assertTrue(result['depthUnitVerified']);self.assertFalse(result['contractSettlementValidated'])
        self.assertAlmostEqual(result['top15BidNotional'],9872)
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_CONTRACT'):validate_contract(self.meta,source_host=SIM)

if __name__=='__main__':unittest.main()
