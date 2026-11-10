import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import agents_status_card

class AgentCardRenderTests(unittest.TestCase):
    def test_status_card_renders_locally_without_telegram(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/"agents.png"
            with patch.object(agents_status_card,"OUT",output):
                path,state=agents_status_card.render()
            self.assertEqual(path,output)
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size,1000)
            self.assertIn("scanner",state)

if __name__=="__main__":
    unittest.main()
