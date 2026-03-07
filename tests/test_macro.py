import unittest

from macro import RecoilMacro


class TestRecoilMacroValidation(unittest.TestCase):
    def setUp(self):
        self.macro = RecoilMacro()

    def test_update_recoil_sanitizes_non_numeric(self):
        self.macro.update_recoil('abc', None)
        self.assertEqual(self.macro.recoil_x, 0.0)
        self.assertEqual(self.macro.recoil_y, 0.0)

    def test_set_multiplier_clamps_bounds(self):
        self.macro.set_multiplier(-10)
        self.assertEqual(self.macro.multiplier, 0.01)

        self.macro.set_multiplier(42)
        self.assertEqual(self.macro.multiplier, 1.0)

    def test_set_multiplier_fallback_default(self):
        self.macro.set_multiplier('nan-value')
        self.assertEqual(self.macro.multiplier, 0.5)


if __name__ == '__main__':
    unittest.main()
