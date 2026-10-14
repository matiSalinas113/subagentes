"""Five login validation tests checked by Git hooks and GitHub Actions."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class HookDemoTests(unittest.TestCase):
    def test_01_accepts_valid_username(self):
        self.assertTrue(app.valid_username("demo_user"))

    def test_02_rejects_empty_username(self):
        self.assertFalse(app.valid_username(""))

    def test_03_rejects_username_with_spaces(self):
        self.assertFalse(app.valid_username("demo user"))

    def test_04_rejects_short_password(self):
        self.assertFalse(app.valid_password("corta"))

    def test_05_accepts_password_with_minimum_length(self):
        self.assertTrue(app.valid_password("a" * 12))


if __name__ == "__main__":
    unittest.main()
