import unittest

from ui_app import Api


class TestApiValidation(unittest.TestCase):
    def test_to_finite_number(self):
        self.assertEqual(Api._to_finite_number('12.5', default=0), 12.5)
        self.assertEqual(Api._to_finite_number('not-a-number', default=7), 7.0)
        self.assertEqual(Api._to_finite_number(float('inf'), default=3), 3.0)

    def test_caps_state_api_method_exists(self):
        api = Api()
        self.assertTrue(hasattr(api, 'get_caps_state'))

        # Must not raise and should return a bool-compatible value.
        value = api.get_caps_state()
        self.assertIsInstance(value, bool)

        api.shutdown()


if __name__ == '__main__':
    unittest.main()
