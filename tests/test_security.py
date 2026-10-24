import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtCore import QLockFile, Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

import main


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        with patch.object(main.MainWindow, 'check_latest_version'), \
                patch.object(main.ConfigManager, 'load', return_value=(tempfile.gettempdir(), '')):
            window = main.MainWindow()
        self.addCleanup(window.close)
        window.version_timer.stop()
        return window

    def test_log_does_not_interpret_remote_markup(self):
        window = self.make_window()
        payload = '<b>forged error</b><img src="file:///private/secret.png">'
        window.append_log(payload)
        self.assertIn(payload, window.log_area.toPlainText())
        self.assertNotIn('<img ', window.log_area.toHtml())

    def test_log_redacts_url_credentials_and_all_token_locations(self):
        window = self.make_window()
        window.append_log('error https://user:password@example.org/path-secret?t=query-secret#fragment-secret')
        text = window.log_area.toPlainText()
        for secret in ('user:', 'password', 'path-secret', 'query-secret', 'fragment-secret'):
            self.assertNotIn(secret, text)
        self.assertIn('https://example.org/[redacted]', text)

    def test_untrusted_labels_are_plain_text(self):
        window = self.make_window()
        for label in (window.lbl_path, window.lbl_latest, window.lbl_status, window.lbl_file):
            self.assertEqual(label.textFormat(), Qt.TextFormat.PlainText)

    def test_redaction_handles_ipv6_and_malformed_urls(self):
        self.assertEqual(main.redact_urls('https://[::1]/secret?q=token'), 'https://[::1]/[redacted]')
        self.assertEqual(main.redact_urls('https://[broken/secret'), '[redacted URL]')

    def test_single_instance_lock_is_exclusive_and_reusable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'app.lock')
            first, second = QLockFile(path), QLockFile(path)
            self.assertTrue(first.tryLock(0))
            try:
                self.assertFalse(second.tryLock(0))
            finally:
                first.unlock()
            self.assertTrue(second.tryLock(0))
            second.unlock()

    def test_channel_confirmation_uses_supported_qt6_enum(self):
        window = self.make_window()
        window.edit_url.setPlainText('https://www.youtube.com/@example')
        window.cb_playlist.setChecked(True)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No), \
                patch.object(window, 'start_next_download') as start:
            window.toggle_main()
            start.assert_not_called()

    def test_pause_keeps_current_item_and_queue(self):
        window = self.make_window()
        window.worker = Mock()
        window.worker.isRunning.return_value = False
        window.total_count = 3
        window.finished_count = 0
        window.pending_urls = ['https://example.org/2', 'https://example.org/3']
        window.is_paused = True
        with patch.object(window, 'start_next_download') as start:
            window.on_one_finished(False, 'paused')
            start.assert_not_called()
        self.assertEqual(window.finished_count, 0)
        self.assertEqual(len(window.pending_urls), 2)

    def test_cancel_does_not_start_next_queued_item(self):
        window = self.make_window()
        window.worker = Mock()
        window.worker.isRunning.return_value = False
        window._cancel_requested = True
        window.pending_urls = []
        with patch.object(window, 'start_next_download') as start:
            window.on_one_finished(False, 'cancelled')
            start.assert_not_called()
        self.assertEqual(window.total_count, 0)


if __name__ == '__main__':
    unittest.main()
