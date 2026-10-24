"""Regression cases for malformed imports, update boundaries and log disclosure."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication
import engine
import main
from connection_settings import private_cookie_file


class AuditRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def response(self, status=200, location=None, chunks=()):
        response = MagicMock()
        response.status_code = status
        response.headers = {'Location': location} if location else {}
        response.iter_content.return_value = chunks
        request = MagicMock()
        request.__enter__.return_value = response
        return request

    def test_deep_cookie_json_becomes_safe_import_error(self):
        source = self.root / 'import.json'
        source.write_text('[' * 2000 + '0' + ']' * 2000)
        with self.assertRaises(ValueError):
            with private_cookie_file(source):
                self.fail('Deep cookie JSON accepted')

    def test_cookie_control_characters_cannot_enter_cookie_jar(self):
        source = self.root / 'import.json'
        for field in ('domain', 'path', 'name', 'value'):
            cookie = dict(domain='.example.test', path='/', name='session', value='synthetic')
            cookie[field] += '\x00'
            source.write_text(json.dumps([cookie]))
            with self.subTest(field=field), self.assertRaises(ValueError):
                with private_cookie_file(source):
                    self.fail('Control character accepted')

    def test_corrupt_and_oversized_manifests_are_uninstalled(self):
        manager = engine.EngineManager(self.root)
        for data in (b'[' * 2000 + b'0' + b']' * 2000, b' ' * 65537):
            (self.root / 'active.json').write_bytes(data)
            self.assertIsNone(manager.installed_version())
            with self.assertRaises(engine.EngineError):
                manager.installed_path()

    def test_corrupt_config_and_wrong_qt_types_fall_back(self):
        config = self.root / 'config.json'
        with patch.object(main, 'CONFIG_FILE', str(config)):
            for data in (b'[' * 2000 + b'0' + b']' * 2000,
                         b' ' * (main.MAX_CONFIG_BYTES + 1), b'[]',
                         b'{"download_path":[],"last_quality":42}'):
                config.write_bytes(data)
                path, quality = main.ConfigManager.load()
                self.assertIsInstance(path, str)
                self.assertIsInstance(quality, str)

    def test_quotes_inside_urls_do_not_leave_secret_suffixes(self):
        for quote in ("'", '"'):
            for url in (f'https://user:pass{quote}secret@example.test/private?token-secret',
                        f'https://example.test/private?token={quote}query-secret'):
                redacted = main.redact_urls(url)
                for secret in ('user:', 'pass', 'secret', 'private'):
                    self.assertNotIn(secret, redacted)

    def test_log_retains_only_approved_recent_lines(self):
        with patch.object(main.MainWindow, 'check_latest_version'), \
                patch.object(main.ConfigManager, 'load', return_value=(self.temp.name, '')):
            window = main.MainWindow()
        window.version_timer.stop()
        try:
            for number in range(2100):
                window.append_log(f'line-{number:04d}')
            self.assertLessEqual(window.log_area.document().blockCount(), 2000)
            self.assertNotIn('line-0000', window.log_area.toPlainText())
            self.assertIn('line-2099', window.log_area.toPlainText())
        finally:
            window.close()

    def test_redirect_is_rejected_before_contacting_untrusted_host(self):
        for location in ('http://github.com/file', 'https://127.0.0.1/private',
                         'https://github.com.attacker.test/file', 'https://user@github.com/file'):
            with self.subTest(location=location), \
                    patch('engine.requests.get', return_value=self.response(302, location)) as get:
                with self.assertRaises(engine.EngineError):
                    with engine._update_response(engine.RELEASE_ROOT):
                        self.fail('Unsafe redirect followed')
                self.assertEqual(get.call_count, 1)

    def test_official_cdn_redirect_and_explicit_public_auth(self):
        location = 'https://release-assets.githubusercontent.com/asset?signed=synthetic'
        with patch('engine.requests.get', side_effect=[self.response(302, location),
                                                       self.response()]) as get:
            with engine._update_response(engine.RELEASE_ROOT):
                pass
            self.assertEqual(get.call_args.args[0], location)
            for call in get.call_args_list:
                self.assertFalse(call.kwargs['allow_redirects'])
                self.assertIsInstance(call.kwargs['auth'], engine._PublicUpdateAuth)

    def test_redirect_loop_is_bounded(self):
        with patch('engine.requests.get', side_effect=lambda *a, **k: self.response(302, engine.RELEASE_ROOT)) as get:
            with self.assertRaises(engine.EngineError):
                with engine._update_response(engine.RELEASE_ROOT):
                    pass
            self.assertEqual(get.call_count, 6)

    def test_release_metadata_size_depth_and_shape_limits(self):
        for content in (b'x' * (engine.MAX_RELEASE_BYTES + 1),
                        b'[' * 2000 + b'0' + b']' * 2000, b'[]',
                        b'{"tag_name":"2026.13.32"}'):
            with self.subTest(size=len(content)), \
                    patch('engine.requests.get', return_value=self.response(chunks=[content])):
                with self.assertRaises(engine.EngineError):
                    engine.EngineManager.latest_release()

    def test_valid_stable_metadata_is_preserved(self):
        release = {'tag_name': '2026.10.21', 'assets': []}
        with patch('engine.requests.get', return_value=self.response(chunks=[json.dumps(release).encode()])):
            self.assertEqual(engine.EngineManager.latest_release(), release)
