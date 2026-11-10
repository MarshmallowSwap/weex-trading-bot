import copy,json,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from weex_depth_evidence import verify,FIELDS
from orderbook_liquidity import parse_book
class EmpiricalUnitsTests(unittest.TestCase):
    def setUp(self):
        self.cert=json.loads(Path(__file__).with_name('weex_depth_unit_evidence.json').read_text())
        self.cert['checkedAt']=datetime.now(timezone.utc).isoformat()
    def inputs(self,s='1000PEPEUSDT'):
        meta=dict(self.cert['symbols'][s]['metadata']);meta['quantityPrecision']=int(meta['quantityPrecision'])
        return meta,{'bids':[['0.0045','1000000']],'asks':[['0.0046','2000000']]}
    def test_validated_multiplied_symbol_has_no_second_multiplier(self):
        meta,book=self.inputs();r=parse_book(meta['symbol'],book,metadata=meta,evidence=self.cert)
        self.assertTrue(r['depthUnitVerified']);self.assertFalse(r['depthUnitOfficiallyConfirmed'])
        self.assertEqual(r['top15BidNotional'],4500);self.assertEqual(r['top15AskNotional'],9200)
        self.assertEqual(r['depthQuantityUnit'],'1000PEPE');self.assertFalse(r['contractValApplied'])
    def test_unseen_symbol_stays_blocked(self):
        meta,book=self.inputs();meta['symbol']='DOGEUSDT'
        self.assertFalse(verify('DOGEUSDT',meta,book,self.cert)[0])
    def test_each_unit_metadata_change_invalidates_evidence(self):
        for key in FIELDS:
            meta,book=self.inputs();meta[key]='CHANGED'
            self.assertFalse(verify('1000PEPEUSDT',meta,book,self.cert)[0])
    def test_stale_or_future_evidence_blocks(self):
        meta,book=self.inputs()
        for delta in (timedelta(days=8),timedelta(seconds=-10)):
            self.cert['checkedAt']=(datetime.now(timezone.utc)-delta).isoformat()
            self.assertFalse(verify(meta['symbol'],meta,book,self.cert)[0])
    def test_runtime_grid_drift_blocks_even_with_old_good_evidence(self):
        meta,book=self.inputs();book['bids'][0][1]='1000001'
        r=parse_book(meta['symbol'],book,metadata=meta,evidence=self.cert)
        self.assertFalse(r['depthUnitVerified']);self.assertIsNone(r['top15BidNotional'])
    def test_weak_ui_evidence_does_not_validate(self):
        meta,book=self.inputs();ui=self.cert['symbols'][meta['symbol']]['uiEvidence']
        ui['bestBaseMatches']=2
        self.assertFalse(verify(meta['symbol'],meta,book,self.cert)[0])
        ui['bestBaseMatches']=18;ui['bestContractConvertedMatches']=1
        self.assertFalse(verify(meta['symbol'],meta,book,self.cert)[0])
    def test_non_discriminating_or_inconsistent_lot_evidence_blocks(self):
        meta,book=self.inputs('BTCUSDT');stats=self.cert['symbols'][meta['symbol']]['restEvidence']
        stats['contractInterpretationStepViolations']=0
        self.assertFalse(verify(meta['symbol'],meta,book,self.cert)[0])
        stats['contractInterpretationStepViolations']=1000;stats['tradeQuoteErrors']=1
        self.assertFalse(verify(meta['symbol'],meta,book,self.cert)[0])
    def test_missing_or_malformed_evidence_never_guesses(self):
        meta,book=self.inputs()
        for data in ({},{'version':1,'checkedAt':'broken'}, {'version':2}):
            self.assertFalse(verify(meta['symbol'],meta,book,data)[0])
        self.assertFalse(parse_book(meta['symbol'],book)['depthUnitVerified'])
    def unit_contract_inputs(self):
        # Synthetic evidence tests the branch; it does not certify a market.
        row=copy.deepcopy(self.cert['symbols']['1000PEPEUSDT'])
        meta=dict(row['metadata'],symbol='UNITUSDT',baseAsset='UNIT',contractVal='1',quantityPrecision='0')
        row['metadata']=meta.copy()
        row['uiEvidence'].update(symbol='UNITUSDT',visibleAmountUnit='UNIT',
                                 bestBaseMatches=18,bestContractConvertedMatches=18)
        self.cert['symbols']['UNITUSDT']=row
        return meta,{'bids':[['0.5','10000']],'asks':[['0.51','20000']]},row
    def test_unit_contract_accepts_independent_ui_matches(self):
        meta,book,row=self.unit_contract_inputs()
        parsed=parse_book(meta['symbol'],book,metadata=meta,evidence=self.cert)
        self.assertTrue(parsed['depthUnitVerified'])
        self.assertEqual(parsed['top15BidNotional'],5000)
        self.assertEqual(parsed['top15AskNotional'],10200)
        self.assertFalse(parsed['depthUnitOfficiallyConfirmed'])
    def test_unit_contract_alone_does_not_certify_book(self):
        meta,book,row=self.unit_contract_inputs()
        for matches in (0,14):
            row['uiEvidence'].update(bestBaseMatches=matches,bestContractConvertedMatches=matches)
            self.assertEqual(verify(meta['symbol'],meta,book,self.cert),(False,'INCONCLUSIVE_UI_EVIDENCE'))
        row['uiEvidence'].update(bestBaseMatches=18,bestContractConvertedMatches=0)
        self.assertFalse(verify(meta['symbol'],meta,book,self.cert)[0])
    def test_unit_contract_still_rejects_stale_changed_or_invalid_evidence(self):
        meta,book,row=self.unit_contract_inputs()
        meta['contractVal']='0.1'
        self.assertFalse(verify('UNITUSDT',meta,book,self.cert)[0])
        meta['contractVal']='1';book['bids'][0][1]='0.5'
        self.assertFalse(verify('UNITUSDT',meta,book,self.cert)[0])
        book['bids'][0][1]='10000'
        self.cert['checkedAt']=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()
        self.assertFalse(verify('UNITUSDT',meta,book,self.cert)[0])
if __name__=='__main__':unittest.main()
