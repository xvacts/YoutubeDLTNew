import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QMimeData
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication

from link_input import LinkInput


class LinkInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.edit = LinkInput()
        self.addCleanup(self.edit.close)

    def paste(self, text):
        mime = QMimeData()
        mime.setText(text)
        self.edit.insertFromMimeData(mime)

    def test_repeated_pastes_are_separate_and_cursor_ready_for_next(self):
        self.paste('https://example.test/one')
        self.paste('https://example.test/two')
        self.assertEqual(self.edit.toPlainText(), 'https://example.test/one\nhttps://example.test/two\n')
        self.assertTrue(self.edit.textCursor().atEnd())
        self.assertEqual(self.edit.textCursor().block().text(), '')

    def test_batch_paste_normalizes_blank_lines_without_changing_url(self):
        self.paste(' https://example.test/a?x=1&x=2 \r\n\r\nhttps://example.test/b#t=4\r\n')
        self.assertEqual(self.edit.toPlainText(), 'https://example.test/a?x=1&x=2\nhttps://example.test/b#t=4\n')

    def test_paste_after_typed_link_does_not_join_links_and_undo_is_atomic(self):
        self.edit.insertPlainText('https://example.test/typed')
        self.paste('https://example.test/pasted')
        self.assertEqual(self.edit.toPlainText(), 'https://example.test/typed\nhttps://example.test/pasted\n')
        self.edit.undo()
        self.assertEqual(self.edit.toPlainText(), 'https://example.test/typed')
        self.edit.redo()
        self.assertTrue(self.edit.toPlainText().endswith('/pasted\n'))

    def test_replace_all_is_one_list_and_one_undo_operation(self):
        self.edit.setPlainText('https://example.test/old')
        self.edit.selectAll()
        self.paste('https://example.test/new')
        self.assertEqual(self.edit.toPlainText(), 'https://example.test/new\n')
        self.edit.undo()
        self.assertEqual(self.edit.toPlainText(), 'https://example.test/old')

    def test_editing_inside_a_url_preserves_inline_edit(self):
        self.edit.setPlainText('https://example.test/path')
        cursor = self.edit.textCursor()
        cursor.setPosition(8)
        self.edit.setTextCursor(cursor)
        self.paste('https://other.test/')
        self.assertNotIn('\n', self.edit.toPlainText())

    def test_rich_clipboard_remains_plain_text(self):
        mime = QMimeData()
        mime.setText('https://example.test/video')
        mime.setHtml('<img src="file:///private/file"><b>https://example.test/video</b>')
        self.edit.insertFromMimeData(mime)
        self.assertEqual(self.edit.toPlainText(), 'https://example.test/video\n')
        self.assertNotIn('<img', self.edit.toHtml())
