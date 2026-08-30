"""
شجرة الملفات المفتوحة: المجلد في الأعلى وملفاته تحته.

تحلّ محلّ شريط التبويبات لأن فتح مجلد كامل يُنتج عشرات الملفات، وهي في شريط
أفقي تتزاحم وتُقصّ أسماؤها. الشجرة تعرضها رأسيًا مجموعةً تحت مجلدها.

الواجهة العامة مطابقة لواجهة الشريط القديم (populate و refresh و select
وإشارتا الاختيار والإغلاق)، فلا يعرف بقيةُ البرنامج أيّهما يستعمل.
"""

from __future__ import annotations

import os

from ..i18n import t

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                               QLabel, QMenu, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from . import icons, theme

INDEX_ROLE = Qt.UserRole + 1


class FileTree(QTreeWidget):
    """ملف لكل صف، مجموعة تحت مجلدها، مع نقطة تعديل وقائمة سياق للإغلاق."""

    fileSelected = Signal(int)
    closeFileRequested = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("FileTree")
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setIndentation(14)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)

        self._guard = False
        self._rows: dict[int, QTreeWidgetItem] = {}

        self.currentItemChanged.connect(self._on_current)
        self.customContextMenuRequested.connect(self._on_menu)

    # -------------------------------------------------------------- المحتوى

    def populate(self, documents):
        self._guard = True
        self.clear()
        self._rows = {}

        groups: dict[str, list] = {}
        for index, doc in enumerate(documents):
            folder = os.path.dirname(doc.path) or doc.path
            groups.setdefault(folder, []).append((index, doc))

        for folder, entries in groups.items():
            parent = QTreeWidgetItem(self)
            parent.setText(0, "%s  (%d)" % (os.path.basename(folder) or folder,
                                            len(entries)))
            parent.setToolTip(0, folder)
            parent.setFont(0, theme.font(9, medium=True))
            parent.setIcon(0, icons.icon("open", 14, theme.TXT_DIM))
            parent.setFlags(Qt.ItemIsEnabled)
            parent.setExpanded(True)

            for index, doc in entries:
                child = QTreeWidgetItem(parent)
                # الأعلام الافتراضية تتضمّن ItemIsUserCheckable، فيرسم Qt
                # مربّع تأشير فارغًا في أول الصف. الملفات تُختار لا تُؤشَّر.
                child.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                child.setData(0, INDEX_ROLE, index)
                self._rows[index] = child
                self._paint(child, doc)

        self._guard = False

    def refresh(self, index, doc):
        item = self._rows.get(index)
        if item is not None:
            self._paint(item, doc)

    def _paint(self, item, doc):
        item.setText(0, doc.name)
        item.setToolTip(0, doc.error or doc.path)
        if doc.error:
            item.setIcon(0, icons.icon("warn", 13, theme.DANGER))
        elif doc.dirty:
            item.setIcon(0, icons.icon("layers", 13, theme.WARN))
        else:
            item.setIcon(0, icons.icon("layers", 13, theme.TXT_MUTE))
        item.setForeground(0, theme.color("WARN" if doc.dirty else "TXT"))

    # ------------------------------------------------------------- الاختيار

    def select(self, index):
        item = self._rows.get(index)
        if item is None or self.currentItem() is item:
            return
        self._guard = True
        self.setCurrentItem(item)
        self.scrollToItem(item)
        self._guard = False

    def _index_of(self, item):
        if item is None:
            return None
        value = item.data(0, INDEX_ROLE)
        return value if isinstance(value, int) else None

    def _on_current(self, item, _previous):
        if self._guard:
            return
        index = self._index_of(item)
        if index is not None:
            self.fileSelected.emit(index)

    def _on_menu(self, point):
        index = self._index_of(self.itemAt(point))
        if index is None:
            return
        menu = QMenu(self)
        action = QAction(t("إغلاق الملف"), menu)
        action.triggered.connect(lambda: self.closeFileRequested.emit(index))
        menu.addAction(action)
        menu.exec(self.viewport().mapToGlobal(point))


class FilePanel(QWidget):
    """غلاف الشجرة بترويسة، ليطابق شكل بقية اللوحات."""

    fileSelected = Signal(int)
    closeFileRequested = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Panel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(7)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("open", 15, theme.TXT_DIM))
        title = QLabel(t("الملفات"))
        title.setObjectName("PanelTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("Hint")
        head.addWidget(glyph)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.count_label)
        outer.addLayout(head)

        self.tree = FileTree()
        self.tree.fileSelected.connect(self.fileSelected)
        self.tree.closeFileRequested.connect(self.closeFileRequested)
        outer.addWidget(self.tree, 1)

    def populate(self, documents):
        self.tree.populate(documents)
        count = len(documents)
        self.count_label.setText(t("%d ملف") % count if count else "")

    def refresh(self, index, doc):
        self.tree.refresh(index, doc)

    def select(self, index):
        self.tree.select(index)
