import unittest
from unittest.mock import patch
import live_test_once_preflight

class LiveTestOnceTelegramTests(unittest.TestCase):
    def test_preview_explicitly_says_no_order_and_shows_gates(self):
        data={
            "status":"PREVIEW_ONLY","symbol":"TAOUSDT","side":"SHORT","volumeRatio":1.2,
            "book":{"depthUnitVerified":True,"liquidityPassed":True},
            "account":{"capacityUsed":0,"capacityMax":3,"manualPositionsExcluded":1,"availableBalanceUSDT":"500"},
            "order":{"costUSDT":"10","costIncludesEntryFee":True,"currentCrossLeverage":"100",
                     "requestedLeverage":"150","minimumLeverage":125,"tpPrice":"1.234",
                     "targetNetProfitUSDT":10},
            "mode":{"tradingMode":"alerts_only","liveSwitch":"RUNNING","executionEnabled":False,
                    "releaseGate":"NO_GO","releasePassed":8,"releaseTotal":9},
            "blockers":["LIVE_RELEASE_NO_GO","TRADING_MODE_ALERTS_ONLY"],
        }
        with patch.object(live_test_once_preflight,"inspect",return_value=data):
            text=live_test_once_preflight.telegram_text()
        self.assertIn("NESSUN ORDINE",text)
        self.assertIn("TAOUSDT SHORT",text)
        self.assertIn("Cost 10 USDT",text)
        self.assertIn("LIVE_RELEASE_NO_GO",text)
        self.assertIn("Ordine inviato: NO.",text)

    def test_wait_report_says_no_order(self):
        with patch.object(live_test_once_preflight,"inspect",
                          return_value={"status":"WAIT","reason":"NO_BOOK_VERIFIED_SIGNAL"}):
            text=live_test_once_preflight.telegram_text()
        self.assertIn("NO_BOOK_VERIFIED_SIGNAL",text)
        self.assertIn("Ordine inviato: NO.",text)

if __name__=="__main__":unittest.main()
