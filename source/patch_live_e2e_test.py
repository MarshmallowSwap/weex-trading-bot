from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\test_live_sdk_end_to_end_audit.py")
s=p.read_text(encoding="utf-8")
s=s.replace('if __name__=="__main__":unittest.main()', ''' def test_empty_never_verified(self):
  import tempfile
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
   result=evaluate([],[],[],Path(d)/"empty.db")
   self.assertEqual(result["state"],"NO_BOT_ORDER_EVIDENCE")
   self.assertFalse(result["canClose"])
if __name__=="__main__":unittest.main()''')
p.write_text(s,encoding="utf-8")
