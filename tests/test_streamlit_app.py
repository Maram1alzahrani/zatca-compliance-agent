from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class StreamlitSmokeTests(unittest.TestCase):
    def test_initial_page_renders_without_exception(self) -> None:
        app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=20).run()
        self.assertEqual([], list(app.exception))
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("ZATCA E-Invoicing Compliance Agent", rendered)
        self.assertEqual(1, len(app.file_uploader))
        self.assertTrue(app.button[0].disabled)


if __name__ == "__main__":
    unittest.main()
