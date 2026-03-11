import unittest
from unittest import mock

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


class TestUpdaterHelpers(unittest.TestCase):
    def test_normalize_version_tag(self):
        self.assertEqual(updater._normalize_version_tag('v2.3.4'), 'v2.3.4')
        self.assertEqual(updater._normalize_version_tag('2.3.4'), 'v2.3.4')
        self.assertIsNone(updater._normalize_version_tag('2.3'))

    def test_parse_latest_manifest_accepts_valid_payload(self):
        manifest = updater._parse_latest_manifest({
            'version': '1.0.23',
            'release_url': 'https://github.com/mmadersbacher/PhantomRecoil/releases/tag/v1.0.23',
            'assets': {
                'portable': {
                    'name': 'Phantom_Recoil_Standalone.exe',
                    'url': 'https://github.com/mmadersbacher/PhantomRecoil/releases/download/v1.0.23/Phantom_Recoil_Standalone.exe',
                    'sha256': 'a' * 64,
                },
                'checksums': {
                    'name': 'SHA256SUMS.txt',
                    'url': 'https://github.com/mmadersbacher/PhantomRecoil/releases/download/v1.0.23/SHA256SUMS.txt',
                },
            },
        })
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest['version'], 'v1.0.23')
        self.assertEqual(manifest['assets']['portable']['name'], 'Phantom_Recoil_Standalone.exe')

    def test_parse_latest_manifest_rejects_missing_binary_assets(self):
        manifest = updater._parse_latest_manifest({
            'version': '1.0.23',
            'assets': {
                'checksums': {
                    'name': 'SHA256SUMS.txt',
                    'url': 'https://example.invalid/SHA256SUMS.txt',
                },
            },
        })
        self.assertIsNone(manifest)

    def test_parse_sha256sums_accepts_filename_then_hash(self):
        text = (
            "Phantom_Recoil_Standalone.exe "
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n"
        )
        parsed = updater._parse_sha256sums(text)
        self.assertIn('Phantom_Recoil_Standalone.exe', parsed)
        self.assertEqual(
            parsed['Phantom_Recoil_Standalone.exe'],
            '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
        )

    def test_parse_sha256sums_accepts_hash_then_filename(self):
        text = (
            "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210 "
            "PhantomRecoilSetup_v1.0.19.exe\n"
        )
        parsed = updater._parse_sha256sums(text)
        self.assertIn('PhantomRecoilSetup_v1.0.19.exe', parsed)
        self.assertEqual(
            parsed['PhantomRecoilSetup_v1.0.19.exe'],
            'fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210',
        )

    def test_select_asset_by_names_case_insensitive(self):
        release_data = {
            'assets': [
                {'name': 'Phantom_Recoil_Standalone.exe', 'browser_download_url': 'https://example.invalid/a'},
            ]
        }
        asset = updater._select_asset_by_names(release_data, ['phantom_recoil_standalone.exe'])
        self.assertIsNotNone(asset)
        self.assertEqual(asset['name'], 'Phantom_Recoil_Standalone.exe')

    def test_select_asset_by_names_handles_invalid_release_payload(self):
        self.assertIsNone(updater._select_asset_by_names(None, ['x']))

    def test_select_installer_asset_prefers_tagged_name(self):
        release_data = {
            'tag_name': 'v1.0.19',
            'assets': [
                {'name': 'PhantomRecoilSetup_v1.0.18.exe', 'browser_download_url': 'https://example.invalid/old'},
                {'name': 'PhantomRecoilSetup_v1.0.19.exe', 'browser_download_url': 'https://example.invalid/new'},
            ],
        }
        asset = updater._select_installer_asset(release_data)
        self.assertIsNotNone(asset)
        self.assertEqual(asset['name'], 'PhantomRecoilSetup_v1.0.19.exe')

    def test_get_latest_update_metadata_prefers_manifest(self):
        with mock.patch('updater._get_latest_manifest', return_value={
            'version': 'v9.9.9',
            'release_url': 'https://example.invalid/release',
            'assets': {'portable': {'name': 'a', 'url': 'https://example.invalid/a'}},
        }):
            metadata = updater._get_latest_update_metadata()
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata['version'], 'v9.9.9')
        self.assertIsNotNone(metadata['manifest'])


if __name__ == '__main__':
    unittest.main()
