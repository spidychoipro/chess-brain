"""폰트/창 테마 회귀 테스트."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtGui import QFontInfo

from ui import theme


class ThemeFontTests(unittest.TestCase):
    def test_no_variable_fonts_in_stylesheet(self):
        for name in ("Noto Sans KR", "Cascadia Mono", "D2Coding"):
            self.assertNotIn(name, theme.STYLESHEET)

    def test_app_font_uses_static_family(self):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        theme.apply(app)
        self.assertEqual(theme.FONT_UI, "Malgun Gothic")
        self.assertEqual(theme.FONT_MONO, "Consolas")
        self.assertEqual(app.font().family(), theme.FONT_UI)
        if app.platformName() == "windows":
            self.assertTrue(QFontInfo(app.font()).exactMatch())


if __name__ == "__main__":
    unittest.main()
