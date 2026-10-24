import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

import main
from connection_settings import ConnectionSettings, private_cookie_file
from workers import DownloadWorker, download_arguments

SYNTHETIC_COOKIES = ('# Netscape HTTP Cookie File\n'
                     '.example.test\tTRUE\t/\tFALSE\t4102444800\tsession\ttest-cookie-value\n')


class ConnectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_window(self, settings=None):
        with patch.object(main.MainWindow, 'check_latest_version'), \
                patch.object(main.ConfigManager, 'load', return_value=(self.temp.name, '')), \
                patch.object(main.ConfigManager, 'load_connection_settings', return_value=settings or ConnectionSettings()):
            window = main.MainWindow()
        window.version_timer.stop()
        self.addCleanup(window.close)
        return window

    def test_proxy_protocols_ipv6_and_validation(self):
        for scheme in ('http', 'socks4', 'socks5'):
            self.assertEqual(ConnectionSettings(use_proxy=True, proxy_type=scheme).proxy_url(),
                             f'{scheme}://127.0.0.1:7890')
        self.assertEqual(ConnectionSettings(use_proxy=True, proxy_ip='::1').proxy_url(), 'http://[::1]:7890')
        for values in ({'proxy_port': '0'}, {'proxy_port': '65536'}, {'proxy_port': '7;exec'},
                       {'proxy_ip': 'user:password@localhost'}, {'proxy_ip': 'http://localhost'},
                       {'proxy_type': 'file'}, {'proxy_ip': 'bad host'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                ConnectionSettings(use_proxy=True, **values).proxy_url()
        self.assertIsNone(ConnectionSettings(use_proxy=False, proxy_port='invalid').proxy_url())

    def test_private_cookie_copy_is_cleaned_and_original_unchanged(self):
        source = self.root / 'export.txt'
        source.write_text(SYNTHETIC_COOKIES, encoding='utf-8')
        original = source.read_bytes()
        with private_cookie_file(source) as path:
            copy = Path(path)
            self.assertNotEqual(copy, source)
            self.assertIn('test-cookie-value', copy.read_text(encoding='utf-8'))
            copy.write_text('changed by downloader', encoding='utf-8')
        self.assertFalse(copy.exists())
        self.assertEqual(source.read_bytes(), original)

    def test_json_cookie_export_converts_to_netscape(self):
        source = self.root / 'export.json'
        source.write_text(json.dumps({'cookies': [{'domain': '.example.test', 'path': '/',
                         'name': 'session', 'value': 'test-cookie-value', 'secure': True,
                         'httpOnly': True, 'expirationDate': 4102444800}]}), encoding='utf-8')
        with private_cookie_file(source) as path:
            text = Path(path).read_text(encoding='utf-8')
            self.assertTrue(text.startswith('# Netscape HTTP Cookie File'))
            self.assertIn('\tsession\ttest-cookie-value', text)
            self.assertIn('#HttpOnly_', text)

    def test_invalid_cookie_errors_do_not_disclose_cookie_contents(self):
        source = self.root / 'invalid.txt'
        for text in ('# Netscape HTTP Cookie File\ninvalid\tprivate-cookie-secret\n',
                     '[{"value":"private-cookie-secret"}]'):
            source.write_text(text, encoding='utf-8')
            with self.assertRaises(ValueError) as error:
                with private_cookie_file(source):
                    self.fail('Malformed cookie export accepted')
            self.assertNotIn('private-cookie-secret', str(error.exception))

    def test_cli_forwards_cookie_and_proxy_as_separate_arguments(self):
        cookie = str(self.root / 'cookie export.txt')
        args = download_arguments('yt-dlp', 'https://example.test/video', str(self.root), 'best', False,
                                  cookie_file=cookie, proxy='socks5://127.0.0.1:1080')
        self.assertEqual(args[args.index('--cookies') + 1], cookie)
        self.assertEqual(args[args.index('--proxy') + 1], 'socks5://127.0.0.1:1080')
        self.assertEqual(args[-2:], ['--', 'https://example.test/video'])
        plain = download_arguments('yt-dlp', 'https://example.test/video', str(self.root), 'best', False)
        self.assertNotIn('--cookies', plain)
        self.assertNotIn('--proxy', plain)

    def test_settings_roundtrip_and_legacy_cookie_preference(self):
        config = self.root / 'config.json'
        settings = ConnectionSettings(cookie_file=str(self.root / 'export.txt'), use_cookie=True,
                                      use_proxy=True, proxy_type='socks5', proxy_port='1080')
        with patch.object(main, 'CONFIG_FILE', str(config)):
            main.ConfigManager.save_connection_settings(settings)
            self.assertEqual(main.ConfigManager.load_connection_settings(), settings)
        stored = config.read_text(encoding='utf-8')
        self.assertNotIn('test-cookie-value', stored)
        self.assertTrue(ConnectionSettings.from_config({'cookie_file': 'old-export.txt'}).use_cookie)
        self.assertFalse(ConnectionSettings.from_config({'cookie_file': 'old-export.txt', 'use_cookie': False}).use_cookie)

    def test_cookie_import_and_proxy_controls_persist_metadata_only(self):
        source = self.root / 'export.txt'
        source.write_text(SYNTHETIC_COOKIES, encoding='utf-8')
        window = self.make_window()
        self.assertFalse(window.proxy_ip_edit.isEnabled())
        with patch.object(main, 'CONFIG_FILE', str(self.root / 'config.json')), \
                patch.object(QFileDialog, 'getOpenFileName', return_value=(str(source), '')):
            window.import_cookie()
            window.cb_proxy.setChecked(True)
            window.proxy_type_combo.setCurrentText('socks5')
            window.proxy_port_edit.setText('1080')
            window.save_proxy_settings()
            stored = main.ConfigManager.load_connection_settings()
        self.assertTrue(window.cb_cookie.isChecked())
        self.assertTrue(window.proxy_ip_edit.isEnabled())
        self.assertEqual(stored.cookie_file, str(source))
        self.assertEqual(stored.proxy_url(), 'socks5://127.0.0.1:1080')
        self.assertNotIn('test-cookie-value', window.log_area.toPlainText())

    def test_invalid_proxy_blocks_download_and_legacy_settings_restore(self):
        window = self.make_window(ConnectionSettings(use_proxy=True, proxy_type='socks4', proxy_port='1080'))
        self.assertEqual(window.proxy_type_combo.currentText(), 'socks4')
        self.assertEqual(window.proxy_port_edit.text(), '1080')
        window.proxy_port_edit.setText('bad')
        window.edit_url.setPlainText('https://example.test/video')
        with patch.object(QMessageBox, 'warning') as warning, patch.object(window, 'start_next_download') as start:
            window.toggle_main()
        warning.assert_called_once()
        start.assert_not_called()

    def test_proxy_urls_are_redacted_in_logs(self):
        text = main.redact_urls('socks5://user:password@proxy.example.test/private?secret=token')
        self.assertEqual(text, 'socks5://proxy.example.test/[redacted]')

    def test_progress_uses_only_display_fields_and_never_dumps_bad_records(self):
        args = download_arguments('yt-dlp', 'https://example.test/video', str(self.root), 'best', False)
        template = args[args.index('--progress-template') + 1]
        self.assertNotIn('%(progress)j', template)
        worker = DownloadWorker('https://example.test/video', str(self.root), 'best')
        logs = []
        worker.log.connect(logs.append)
        worker._line('__YTDLP_PROGRESS__invalid-private-cookie-secret')
        self.assertTrue(logs)
        self.assertNotIn('private-cookie-secret', '\n'.join(logs))


if __name__ == '__main__':
    unittest.main()
