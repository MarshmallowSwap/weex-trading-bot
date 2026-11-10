import unittest
from decimal import Decimal
from commands import build

class CommandReportTests(unittest.TestCase):
    def setUp(self):
        self.data=([],Decimal("12.5"),Decimal("0.25"),2,1,0)
    def test_pnl_report_is_built_locally(self):
        kind,fields,caption=build("/pnl",self.data)
        self.assertEqual(kind,"pnl")
        self.assertEqual(dict(fields)["PNL NETTO"],"+12.2500 USDT")
        self.assertIn("Funding",caption)
    def test_winrate_report_is_built_locally(self):
        kind,fields,caption=build("/winrate",self.data)
        self.assertEqual(kind,"winrate")
        self.assertEqual(dict(fields)["RATE"],"66.67%")
        self.assertIn("non storico completo",caption)

if __name__=="__main__":
    unittest.main()
