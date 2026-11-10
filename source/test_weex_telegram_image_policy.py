"""Offline tests: all execution notifications are graphical, including break-even."""
import json,unittest
from unittest.mock import patch
from weex_fill_alerts import display,transport
from weex_neutral_fill_card import render_neutral_fill
import monitor
SUMMARY={'symbol':'ETHUSDT','positionSide':'LONG','side':'SELL','orderId':'11',
'action':'CLOSE','quantity':'2','quoteQty':'200','averagePrice':'100',
'realizedPnl':'0','fees':{'USDT':'0.16'},'fillCount':2,'lastTime':1793925588340}
FILL={'id':'22','symbol':'ETHUSDT','positionSide':'LONG','side':'SELL',
'qty':'2','price':'100','realizedPnl':'0','time':1793925588340}
CFG={'telegram_chat_id':'simulated','telegram_bot_token':'not-a-real-token'}
class Response:
 def __init__(self,reply):self.reply=reply
 def __enter__(self):return self
 def __exit__(self,*a):return False
 def read(self,*a):return json.dumps(self.reply).encode()
def observed(_root,_source,_method,_content,send):return send()
class GraphicalFillTests(unittest.TestCase):
 def test_close_zero_is_neutral_not_profit(self):
  self.assertEqual(display(SUMMARY)[0],'neutral')
  self.assertEqual(display({**SUMMARY,'realizedPnl':'1'})[0],'profit')
  self.assertEqual(display({**SUMMARY,'realizedPnl':'-1'})[0],'loss')
 def test_neutral_image_is_png(self):
  self.assertTrue(render_neutral_fill(FILL,'close','LONG').startswith(bytes((137,80,78,71))))
 def test_aggregate_zero_posts_png_not_text(self):
  seen=[]
  def network(request,timeout):
   seen.append((request.full_url,request.data))
   return Response({'ok':True,'result':{'message_id':142}})
  with patch('weex_alert_archive.observed',side_effect=observed),patch('weex_fill_alerts.urllib.request.urlopen',side_effect=network):
   self.assertEqual(transport(None,CFG,SUMMARY),142)
  self.assertEqual(len(seen),1)
  self.assertTrue(seen[0][0].endswith('/sendPhoto'))
  self.assertIn(b'image/png',seen[0][1])
  self.assertIn(bytes((137,80,78,71)),seen[0][1])
 def test_aggregate_edit_remains_photo_png(self):
  seen=[]
  def network(request,timeout):
   seen.append((request.full_url,request.data))
   return Response({'ok':True,'result':{'message_id':142}})
  with patch('weex_alert_archive.observed',side_effect=observed),patch('weex_fill_alerts.urllib.request.urlopen',side_effect=network):
   self.assertEqual(transport(None,CFG,SUMMARY,142),142)
  self.assertEqual(len(seen),1)
  self.assertTrue(seen[0][0].endswith('/editMessageMedia'))
  self.assertIn(b'image/png',seen[0][1])
 def test_single_zero_fill_photo_not_text(self):
  seen=[]
  with patch('weex_alert_archive.photo_sender',side_effect=lambda fn,*a,**k:fn),patch('telegram_position_reports.send_image',side_effect=lambda cfg,data,caption:seen.append((data,caption))):
   monitor.send(FILL,CFG)
  self.assertEqual(len(seen),1)
  self.assertTrue(seen[0][0].startswith(bytes((137,80,78,71))))
  self.assertIn('PnL fill',seen[0][1])
 def test_no_text_fallback_after_photo_failure(self):
  def fail(*a,**k):raise RuntimeError('DELIVERY_UNKNOWN')
  with patch('weex_alert_archive.photo_sender',side_effect=lambda fn,*a,**k:fn),patch('telegram_position_reports.send_image',side_effect=fail):
   with self.assertRaisesRegex(RuntimeError,'DELIVERY_UNKNOWN'):
    monitor.send(FILL,CFG)
if __name__=='__main__':unittest.main()
