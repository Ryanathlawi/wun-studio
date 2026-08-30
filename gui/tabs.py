"""
شريط تبويبات الملفات المفتوحة.

مبني على QTabBar لا على رسم يدوي، فيرث مجانًا التمرير عند كثرة التبويبات
والتنقل بلوحة المفاتيح وسلوك الإغلاق المتوقّع في أي محرر.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTabBar, QWidget


class FileTabs(QTabBar):
    """تبويب لكل ملف مفتوح، مع نقطة تعديل وزر إغلاق."""

    fileSelected = Signal(int)
    closeFileRequested = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("FileTabs")
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setMovable(False)
        self.setTabsClosable(True)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.ElideMiddle)
        self.setFocusPolicy(Qt.NoFocus)

        self._guard = False
        self.currentChanged.connect(self._on_current)
        self.tabCloseRequested.connect(self.closeFileRequested)

    # -------------------------------------------------------------- المحتوى

    def populate(self, documents):
        self._guard = True
        while self.count():
            self.removeTab(0)
        for doc in documents:
            index = self.addTab(self._label(doc))
            self.setTabToolTip(index, doc.path)
        self._guard = False

    def refresh(self, index, doc):
        if 0 <= index < self.count():
            self.setTabText(index, self._label(doc))
            self.setTabToolTip(index, doc.error or doc.path)

    @staticmethod
    def _label(doc) -> str:
        # النقطة تسبق الاسم في العربية فتقع بصريًا في أول التبويب
        return ("● " if doc.dirty else "") + doc.name

    def select(self, index):
        if 0 <= index < self.count() and self.currentIndex() != index:
            self._guard = True
            self.setCurrentIndex(index)
            self._guard = False

    def _on_current(self, index):
        if not self._guard and index >= 0:
            self.fileSelected.emit(index)
