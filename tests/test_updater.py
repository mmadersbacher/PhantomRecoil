import unittest

import updater


class TestUpdaterVersionParsing(unittest.TestCase):
    def test_parse_version_accepts_prefixed(self):
        self.assertEqual(updater._parse_version('v1.2.3'), (1, 2, 3))

    def test_parse_version_accepts_unprefixed(self):
        self.assertEqual(updater._parse_version('1.2.3'), (1, 2, 3))

    def test_parse_version_rejects_invalid(self):
        self.assertIsNone(updater._parse_version('v1.2'))
        self.assertIsNone(updater._parse_version('latest'))

    def test_newer_version_compare(self):
        self.assertTrue(updater._is_newer_version('v1.0.0', 'v1.0.1'))
        self.assertFalse(updater._is_newer_version('v1.1.0', 'v1.0.9'))
        self.assertFalse(updater._is_newer_version('v1.1.0', 'invalid'))


if __name__ == '__main__':
    unittest.main()
