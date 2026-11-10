import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import settings_card

class SettingsCardRenderTests(unittest.TestCase):
    def test_settings_card_renders_locally_without_telegram(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/"settings.png"
            with patch.object(settings_card,"OUT",output):
                path=settings_card.render()
            self.assertEqual(path,output)
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size,1000)

if __name__=="__main__":
    unittest.main()
