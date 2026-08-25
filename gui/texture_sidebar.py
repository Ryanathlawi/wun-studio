"""Left sidebar: the texture list with thumbnails."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QVBoxLayout, QWidget)

from .canvas import numpy_to_qimage

THUMB = 56


def _placeholder(text="!"):
    pm = QPixmap(THUMB, THUMB)
    pm.fill(QColor(45, 46, 50))
    p = QPainter(pm)
    p.setPen(QColor(180, 120, 90))
    p.drawRect(0, 0, THUMB - 1, THUMB - 1)
    p.drawText(pm.rect(), Qt.AlignCenter, text)
    p.end()
    return QIcon(pm)


def _thumb_icon(arr):
    """Build a checkerboard-backed thumbnail so alpha is visible in the list."""
    img = numpy_to_qimage(arr).scaled(THUMB, THUMB, Qt.KeepAspectRatio,
                                      Qt.SmoothTransformation)
    pm = QPixmap(THUMB, THUMB)
    pm.fill(QColor(52, 53, 57))
    p = QPainter(pm)
    for y in range(0, THUMB, 8):
        for x in range(0, THUMB, 8):
            if ((x // 8) + (y // 8)) % 2 == 0:
                p.fillRect(x, y, 8, 8, QColor(62, 63, 68))
    p.drawImage((THUMB - img.width()) // 2, (THUMB - img.height()) // 2, img)
    p.end()
    return QIcon(pm)


class TextureSidebar(QWidget):
    """Searchable list of the textures inside the open dictionary."""

    textureSelected = Signal(int)          # texture index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter textures...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.setIconSize(QSize(THUMB, THUMB))
        self.list.setUniformItemSizes(False)
        self.list.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self.list, 1)

        self.summary = QLabel("No file loaded")
        self.summary.setProperty("hint", True)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

    # ------------------------------------------------------------- content

    def clear(self):
        self._entries = []
        self.list.clear()
        self.summary.setText("No file loaded")

    def populate(self, ytd, progress=None):
        """Fill the list from a loaded YtdFile."""
        self.list.blockSignals(True)
        self.list.clear()
        self._entries = list(ytd.textures)

        broken = 0
        for i, entry in enumerate(self._entries):
            if progress is not None:
                progress(i, len(self._entries))

            item = QListWidgetItem()
            item.setText("%s\n%dx%d  %s" % (entry.name, entry.width,
                                            entry.height, entry.format_name))
            item.setData(Qt.UserRole, entry.index)
            item.setSizeHint(QSize(0, THUMB + 12))

            if entry.editable:
                try:
                    item.setIcon(_thumb_icon(ytd.thumbnail(entry, THUMB)))
                except Exception:
                    item.setIcon(_placeholder("?"))
            else:
                broken += 1
                item.setIcon(_placeholder("!"))
                item.setForeground(QColor(200, 140, 110))
                item.setToolTip(entry.error)
            if not item.toolTip():
                item.setToolTip(entry.describe())
            self.list.addItem(item)

        self.list.blockSignals(False)

        msg = "%d texture%s" % (len(self._entries),
                                "" if len(self._entries) == 1 else "s")
        if broken:
            msg += "  -  %d unsupported" % broken
        self.summary.setText(msg)

        if self.list.count():
            for row in range(self.list.count()):
                entry = self._entry_for_row(row)
                if entry is not None and entry.editable:
                    self.list.setCurrentRow(row)
                    break
            else:
                self.list.setCurrentRow(0)

    def _entry_for_row(self, row):
        item = self.list.item(row)
        if item is None:
            return None
        idx = item.data(Qt.UserRole)
        for entry in self._entries:
            if entry.index == idx:
                return entry
        return None

    def mark_edited(self, index, edited=True):
        """Show a dot next to textures with unsaved changes."""
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(Qt.UserRole) != index:
                continue
            text = item.text()
            has_dot = text.startswith("● ")
            if edited and not has_dot:
                item.setText("● " + text)
            elif not edited and has_dot:
                item.setText(text[2:])
            return

    def select_index(self, index):
        for row in range(self.list.count()):
            if self.list.item(row).data(Qt.UserRole) == index:
                self.list.setCurrentRow(row)
                return

    # -------------------------------------------------------------- events

    def _apply_filter(self, text):
        needle = text.strip().lower()
        for row in range(self.list.count()):
            item = self.list.item(row)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_current_changed(self, current, _previous):
        if current is not None:
            self.textureSelected.emit(current.data(Qt.UserRole))
