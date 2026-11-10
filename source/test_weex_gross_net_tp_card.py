"""Offline check: TP gross and estimated net appear only on exact bot-owned position."""
import unittest
from weex_position_reports import open_rows
from weex_position_cards import render
POSITION={'id':'bot-position-7','symbol':'ETHUSDT','side':'LONG','size':'2',
 'asset':'USDT','leverage':'125','openValue':'200','unrealizePnl':'1','marginType':'CROSSED'}
TP={'symbol':'ETHUSDT','positionSide':'LONG','side':'SELL',
 'reduceOnly':True,'orderType':'TAKE_PROFIT_MARKET','algoStatus':'UNTRIGGERED',
 'triggerPrice':'110.00','workingType':'MARK_PRICE','quantity':'2','closePosition':False}
PREVIEW={'mode':'PNL_GROSS_BEFORE_COSTS_USDT','targetGrossUSDT':'20',
 'triggerPrice':'110.00','estimatedNetAfterFeesSlippageUSDT':'19.664',
 'ownedQuantity':'2','ownedEntryCostUSDT':'200','ownedEntryFeesUSDT':'0.16',
 'ownedTpRequest':{'symbol':'ETHUSDT','positionSide':'LONG','triggerPrice':'110.00',
                   'triggerPriceType':'MARK_PRICE','quantity':'2','reduceOnly':True}}
class GrossNetCard(unittest.TestCase):
 def test_exact_owned_full_tp_displays_both(self):
  rows=open_rows([POSITION],[TP],tp_previews={('ETHUSDT','bot-position-7'):PREVIEW})
  self.assertEqual(rows[0]['tpGrossTargetUSDT'],'20')
  self.assertEqual(rows[0]['tpNetEstimatedUSDT'],'19.664')
  img=render({'kind':'open','rows':rows,'observedAtMs':10000000,
   'stale':False,'partialRealized':'0','windowEndMs':10000000})
  self.assertEqual(len(img),1)
  self.assertTrue(img[0].startswith(b'\x89PNG'))
 def test_manual_not_attributed(self):
  rows=open_rows([POSITION],[TP],tp_previews={('ETHUSDT','different-id'):PREVIEW})
  self.assertNotIn('tpNetEstimatedUSDT',rows[0])
 def test_no_verified_full_tp_no_preview(self):
  bad={**TP,'quantity':'1'}
  rows=open_rows([POSITION],[bad],tp_previews={('ETHUSDT','bot-position-7'):PREVIEW})
  self.assertNotIn('tpNetEstimatedUSDT',rows[0])
 def test_modified_entry_economics_no_preview(self):
  changed={**POSITION,'openValue':'201'}
  rows=open_rows([changed],[TP],tp_previews={('ETHUSDT','bot-position-7'):PREVIEW})
  self.assertNotIn('tpNetEstimatedUSDT',rows[0])
 def test_modified_entry_fees_no_preview(self):
  changed={**POSITION,'openFee':'0.3'}
  rows=open_rows([changed],[TP],tp_previews={('ETHUSDT','bot-position-7'):PREVIEW})
  self.assertNotIn('tpNetEstimatedUSDT',rows[0])
 def test_multiple_tp_no_preview(self):
  more={**TP,'triggerPrice':'109.00'}
  rows=open_rows([POSITION],[TP,more],tp_previews={('ETHUSDT','bot-position-7'):PREVIEW})
  self.assertNotIn('tpNetEstimatedUSDT',rows[0])
 def test_changed_working_type_no_preview(self):
  changed={**TP,'workingType':'CONTRACT_PRICE'}
  rows=open_rows([POSITION],[changed],tp_previews={('ETHUSDT','bot-position-7'):PREVIEW})
  self.assertNotIn('tpNetEstimatedUSDT',rows[0])
 def test_changed_quantity_no_preview(self):
  changed={**POSITION,'size':'3','openValue':'300'}
  rows=open_rows([changed],[TP],tp_previews={('ETHUSDT','bot-position-7'):PREVIEW})
  self.assertNotIn('tpNetEstimatedUSDT',rows[0])
 def test_tp_price_changed_no_preview(self):
  bad={**TP,'triggerPrice':'111.00'}
  rows=open_rows([POSITION],[bad],tp_previews={('ETHUSDT','bot-position-7'):PREVIEW})
  self.assertNotIn('tpNetEstimatedUSDT',rows[0])
if __name__=='__main__':unittest.main()
