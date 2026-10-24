"""Plain-text link entry with one paste per line and a single undo step."""
import re

from PyQt6.QtGui import QTextBlockFormat
from PyQt6.QtWidgets import QTextEdit


class LinkInput(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('LinkInput')
        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)
        block = QTextBlockFormat()
        block.setLineHeight(145, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        cursor = self.textCursor()
        cursor.setBlockFormat(block)
        self.setTextCursor(cursor)
        self.document().setDocumentMargin(4)

    def insertFromMimeData(self, source):
        lines = [line.strip() for line in source.text().splitlines() if line.strip()]
        cursor = self.textCursor()
        replace_all = (cursor.hasSelection() and cursor.selectionStart() == 0
                       and cursor.selectionEnd() == self.document().characterCount()-1)
        append_links = (not cursor.hasSelection() and cursor.atBlockEnd()) or replace_all
        if (not self.isReadOnly() and append_links and lines
                and all(re.fullmatch(r'https?://\S+', line, re.IGNORECASE) for line in lines)):
            # Keep edits inside an existing URL literal; automatic separation is
            # for adding links at the end of a line or replacing the whole list.
            prefix = '\n' if not replace_all and cursor.block().text().strip() else ''
            cursor.beginEditBlock()
            cursor.insertText(prefix + '\n'.join(lines) + '\n')
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            return
        super().insertFromMimeData(source)
