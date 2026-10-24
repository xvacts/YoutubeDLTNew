import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from engine import EngineError, EngineManager, asset_name, child_environment, version_tuple
from workers import download_arguments


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manager = EngineManager(self.temp.name)

    def release(self, version='2026.10.21', payload=b'official-binary'):
        return {'tag_name': version, 'assets': [{
            'name': self.manager.asset, 'size': len(payload),
            'digest': 'sha256:' + hashlib.sha256(payload).hexdigest(),
            'browser_download_url': f'https://github.com/yt-dlp/yt-dlp/releases/download/{version}/{self.manager.asset}',
        }]}

    def install(self, release=None, payload=b'official-binary', returncode=0):
        release = release or self.release(payload=payload)
        response = MagicMock()
        response.url = release['assets'][0]['browser_download_url']
        response.status_code = 200
        response.iter_content.return_value = [payload]
        request = MagicMock()
        request.__enter__.return_value = response
        process = MagicMock()
        process.__enter__.return_value = process
        process.returncode = returncode
        process.communicate.return_value = (release['tag_name'] + '\n', '')
        with patch.object(self.manager, 'latest_release', return_value=release), \
                patch('engine.requests.get', return_value=request), \
                patch('processes.start_process', return_value=process) as spawn, \
                patch('processes.ProcessTree'):
            result = self.manager.ensure(update=True)
        return result, spawn

    def test_verified_install_and_tampering_detection(self):
        with self.manager.exclusive():
            path, spawn = self.install()
        self.assertEqual(path, self.manager.installed_path())
        self.assertEqual(self.manager.installed_version(), '2026.10.21')
        self.assertIn('--ignore-config', spawn.call_args.args[0])
        path.write_bytes(b'tampered')
        with self.assertRaises(EngineError):
            self.manager.installed_path()

    def test_hash_failure_preserves_old_active_binary(self):
        old, _ = self.install(self.release('2026.7.4'))
        before = (self.manager.root / 'active.json').read_bytes()
        with patch('processes.start_process') as spawn:
            with self.assertRaises(EngineError):
                self.install(self.release(payload=b'expected-binary'), payload=b'tampered-binary')
            spawn.assert_not_called()
        self.assertEqual((self.manager.root / 'active.json').read_bytes(), before)
        self.assertEqual(self.manager.installed_path(), old)

    def test_failed_startup_preserves_previous_version(self):
        old, _ = self.install(self.release('2026.7.4'))
        with self.assertRaises(EngineError):
            self.install(returncode=1)
        self.assertEqual(self.manager.installed_path(), old)

    def test_existing_install_does_not_need_network(self):
        path, _ = self.install()
        with patch.object(self.manager, 'latest_release') as fetch:
            self.assertEqual(self.manager.ensure(), path)
            fetch.assert_not_called()

    def test_no_downgrade_or_unofficial_asset_url(self):
        self.install()
        with self.assertRaises(EngineError):
            self.install(self.release('2026.7.4'))
        release = self.release()
        release['assets'][0]['browser_download_url'] = 'https://example.org/evil.exe'
        with self.assertRaises(EngineError):
            self.install(release)

    def test_no_execution_without_official_digest(self):
        release = self.release()
        release['assets'][0].pop('digest')
        with self.assertRaises(EngineError):
            self.install(release)

    def test_manifest_cannot_traverse_directories(self):
        (self.manager.root / 'active.json').write_text(json.dumps({
            'version': '../../outside', 'asset': '../evil', 'sha256': '0' * 64}))
        self.assertIsNone(self.manager.installed_version())
        with self.assertRaises(EngineError):
            self.manager.installed_path()

    def test_exclusive_update_download_lock(self):
        other = EngineManager(self.temp.name)
        with self.manager.exclusive():
            with self.assertRaises(EngineError):
                with other.exclusive():
                    self.fail('two engine operations held the same lock')

    def test_platform_assets_and_version_floor(self):
        self.assertEqual(asset_name('Windows', 'AMD64'), 'yt-dlp.exe')
        self.assertEqual(asset_name('Windows', 'ARM64'), 'yt-dlp_arm64.exe')
        self.assertEqual(asset_name('Darwin', 'arm64'), 'yt-dlp_macos')
        with self.assertRaises(EngineError):
            version_tuple('2025.10.14')

    def test_cli_preserves_url_boundary_and_audio_playlist_options(self):
        url = 'https://example.org/video?name=";echo injected'
        args = download_arguments('/trusted/yt-dlp', url, self.temp.name, '仅音频（MP3 192kbps）', True)
        self.assertEqual(args[-2:], ['--', url])
        for arg in ('--ignore-config', '--no-plugin-dirs', '--no-update', '--yes-playlist', '--extract-audio'):
            self.assertIn(arg, args)
        self.assertEqual(args[args.index('--audio-quality') + 1], '192K')
        self.assertTrue(Path(args[args.index('--output') + 1]).is_absolute())

    def test_child_does_not_inherit_python_or_pyinstaller_environment(self):
        with patch.dict(os.environ, {'PYTHONPATH': 'unsafe', '_PYI_PARENT_PROCESS_LEVEL': '2',
                                     'QT_PLUGIN_PATH': 'unsafe'}, clear=False):
            env = child_environment()
        self.assertNotIn('PYTHONPATH', env)
        self.assertNotIn('_PYI_PARENT_PROCESS_LEVEL', env)
        self.assertNotIn('QT_PLUGIN_PATH', env)
        self.assertEqual(env['PYINSTALLER_RESET_ENVIRONMENT'], '1')


if __name__ == '__main__':
    unittest.main()
