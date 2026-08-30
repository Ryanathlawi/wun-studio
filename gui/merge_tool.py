"""
أداة دمج الموارد.

تأخذ عدة موارد FiveM — ملابس أو سيارات أو خرائط — وتجمع محتوى مجلدات
stream كلها في مورد واحد، وتولّد له fxmanifest.lua يجمع إعدادات الأصول.
تصادم الأسماء يُكتشف ويُعرض قبل التنفيذ، والموارد الأصلية لا تُلمس.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QApplication, QCheckBox, QFileDialog,
                               QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QProgressDialog, QSplitter, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core import merge
from . import icons, theme
from .properties import _button
from .widgets import Divider, EmptyState


def _size(value):
    if value >= 1e9:
        return "%.2f جيجا" % (value / 1e9)
    return "%.0f م.ب" % (value / 1e6)


class MergeTool(QWidget):
    """واجهة دمج عدة موارد في مورد واحد."""

    statusMessage = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.paths = []
        self.resources = []
        self.plan = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 4, 10, 10)
        outer.setSpacing(9)

        outer.addWidget(self._build_bar())
        outer.addWidget(self._build_body(), 1)
        outer.addWidget(self._build_footer())

    # --------------------------------------------------------------- البناء

    def _build_bar(self):
        bar = QWidget()
        bar.setFixedHeight(46)
        row = QHBoxLayout(bar)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(7)

        self.btn_add = _button("أضف موردًا…", "open", "primary",
                               "اختر مجلد المورد (الذي يحوي stream)")
        self.btn_add.clicked.connect(self.add_resource)
        row.addWidget(self.btn_add)

        self.btn_remove = _button("احذف المحدَّد", "trash")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_remove.setEnabled(False)
        row.addWidget(self.btn_remove)

        self.btn_clear = _button("تفريغ", "close")
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_clear.setEnabled(False)
        row.addWidget(self.btn_clear)

        row.addWidget(Divider(vertical=True))

        name_label = QLabel("اسم المورد الناتج")
        name_label.setObjectName("PanelTitle")
        row.addWidget(name_label)
        self.name_field = QLineEdit("athlawi_clothing")
        self.name_field.setFixedHeight(34)
        self.name_field.setFixedWidth(230)
        self.name_field.setLayoutDirection(Qt.LeftToRight)
        self.name_field.textChanged.connect(self._refresh_manifest)
        row.addWidget(self.name_field)

        self.move_check = QCheckBox("انقل بدل النسخ")
        self.move_check.setToolTip(
            "أسرع ولا يحتاج مساحة إضافية، لكنه يُفرِّغ الموارد الأصلية.")
        row.addWidget(self.move_check)

        row.addStretch(1)
        return bar

    def _build_body(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(9)

        left = QWidget()
        left.setObjectName("Panel")
        column = QVBoxLayout(left)
        column.setContentsMargins(10, 10, 10, 10)
        column.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(7)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("layers", 15, theme.TXT_DIM))
        title = QLabel("الموارد المضافة")
        title.setObjectName("PanelTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("Hint")
        head.addWidget(glyph)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.count_label)
        column.addLayout(head)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["المورد", "ملفات", "الحجم"])
        self.tree.setIndentation(16)
        self.tree.itemSelectionChanged.connect(self._on_selection)
        column.addWidget(self.tree, 1)

        self.empty = EmptyState(
            "layers", "لم يُضَف أي مورد",
            "أضف مجلدات الموارد التي تريد دمجها. كل مورد يجب أن يحوي مجلد "
            "stream بداخله.")
        column.addWidget(self.empty, 1)
        self.tree.hide()
        splitter.addWidget(left)

        right = QWidget()
        right.setObjectName("Panel")
        right_column = QVBoxLayout(right)
        right_column.setContentsMargins(10, 10, 10, 10)
        right_column.setSpacing(8)

        manifest_head = QHBoxLayout()
        manifest_head.setSpacing(7)
        glyph2 = QLabel()
        glyph2.setPixmap(icons.pixmap("text", 15, theme.TXT_DIM))
        title2 = QLabel("fxmanifest.lua المولّد")
        title2.setObjectName("PanelTitle")
        manifest_head.addWidget(glyph2)
        manifest_head.addWidget(title2)
        manifest_head.addStretch(1)
        right_column.addLayout(manifest_head)

        self.manifest_view = QPlainTextEdit()
        self.manifest_view.setReadOnly(True)
        self.manifest_view.setLayoutDirection(Qt.LeftToRight)
        self.manifest_view.setFont(theme.font(9))
        right_column.addWidget(self.manifest_view, 1)
        splitter.addWidget(right)

        splitter.setSizes([720, 460])
        return splitter

    def _build_footer(self):
        bar = QWidget()
        bar.setFixedHeight(44)
        row = QHBoxLayout(bar)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(7)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("Hint")
        row.addWidget(self.summary_label)
        row.addStretch(1)

        self.btn_merge = _button("ادمج في مورد واحد…", "batch", "primary")
        self.btn_merge.clicked.connect(self.do_merge)
        self.btn_merge.setEnabled(False)
        row.addWidget(self.btn_merge)
        return bar

    # -------------------------------------------------------------- الموارد

    def add_resource(self):
        folder = QFileDialog.getExistingDirectory(
            self, "اختر مجلد المورد (الذي يحوي stream)")
        if not folder:
            return
        folder = os.path.abspath(folder)
        if folder in self.paths:
            return
        self.paths.append(folder)
        self.rescan()

    def remove_selected(self):
        for item in self.tree.selectedItems():
            if item.parent() is not None:
                continue
            path = item.data(0, Qt.UserRole)
            if path in self.paths:
                self.paths.remove(path)
        self.rescan()

    def clear_all(self):
        self.paths = []
        self.rescan()

    def rescan(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.resources = merge.scan(self.paths)
            self.plan = merge.plan(self.resources)
        finally:
            QApplication.restoreOverrideCursor()
        self._populate()

    def _populate(self):
        self.tree.clear()
        for resource in self.resources:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, resource.name)
            item.setData(0, Qt.UserRole, resource.path)
            item.setToolTip(0, resource.path)
            item.setFont(0, theme.font(10, medium=True))
            if resource.error:
                item.setText(2, resource.error)
                item.setIcon(0, icons.icon("warn", 14, theme.DANGER))
                continue
            item.setText(1, "%d" % len(resource.stream_files))
            item.setText(2, _size(resource.stream_bytes))
            item.setIcon(0, icons.icon("layers", 14, theme.ACCENT))

            detail = QTreeWidgetItem(item)
            detail.setText(0, "manifest: %s   ·   ملفات جذر: %s"
                           % (resource.manifest_name or "لا يوجد",
                              "، ".join(resource.root_files) or "لا شيء"))
            detail.setForeground(0, theme.color("TXT_MUTE"))
            if resource.has_scripts:
                warn = QTreeWidgetItem(item)
                warn.setText(0, "⚠ هذا المورد فيه سكربتات — راجعها يدويًا "
                                "بعد الدمج")
                warn.setForeground(0, theme.color("WARN"))

        if self.plan and self.plan.stream_clashes:
            clash = QTreeWidgetItem(self.tree)
            clash.setText(0, "تصادم أسماء — %d ملف"
                          % len(self.plan.stream_clashes))
            clash.setIcon(0, icons.icon("warn", 14, theme.WARN))
            clash.setFont(0, theme.font(10, medium=True))
            for name, first, second in self.plan.stream_clashes[:200]:
                child = QTreeWidgetItem(clash)
                child.setText(0, name)
                child.setText(2, "يُؤخذ من %s ويُتجاهل من %s" % (first, second))
                child.setForeground(0, theme.color("TXT_DIM"))

        has = bool(self.resources)
        self.tree.setVisible(has)
        self.empty.setVisible(not has)
        self.btn_clear.setEnabled(has)
        self.count_label.setText("%d" % len(self.resources))

        if self.plan:
            stats = merge.summary(self.plan)
            self.summary_label.setText(
                "%d مورد · %d ملف فريد · %s · تصادم %d"
                % (stats["resources"], stats["files"], _size(stats["bytes"]),
                   stats["stream_clashes"]))
            self.btn_merge.setEnabled(stats["files"] > 0)
        else:
            self.summary_label.setText("")
            self.btn_merge.setEnabled(False)
        self._refresh_manifest()

    def _refresh_manifest(self):
        if not self.plan or not self.plan.resources:
            self.manifest_view.setPlainText("")
            return
        self.manifest_view.setPlainText(
            self.plan.manifest(self.name_field.text().strip() or "merged",
                               theme.AUTHOR))

    def _on_selection(self):
        top = [i for i in self.tree.selectedItems() if i.parent() is None]
        self.btn_remove.setEnabled(bool(top))

    # -------------------------------------------------------------- التنفيذ

    def do_merge(self):
        from .main_window import ask, show_info

        name = self.name_field.text().strip()
        if not name:
            show_info(self, "اسم ناقص", "اكتب اسمًا للمورد الناتج.")
            return

        out = QFileDialog.getExistingDirectory(
            self, "اختر المجلد الذي يُنشأ فيه المورد الناتج")
        if not out:
            return

        target = os.path.join(out, name)
        for resource in self.plan.resources:
            if os.path.abspath(target) == resource.path:
                show_info(self, "اختر مجلدًا آخر",
                          "المسار الناتج يطابق أحد الموارد المصدر.")
                return
        if os.path.exists(target) and os.listdir(target):
            if not ask(self, "المجلد موجود",
                       "المجلد «%s» موجود وغير فارغ. المتابعة قد تخلط "
                       "الملفات.\n\nهل تتابع؟" % target, "تابع", warning=True):
                return

        stats = merge.summary(self.plan)
        moving = self.move_check.isChecked()
        warning = ""
        if moving:
            warning = ("\n\n⚠ وضع النقل مفعّل: ستُفرَّغ مجلدات stream في "
                       "الموارد الأصلية ولا يمكن التراجع.")
        if stats["scripts"]:
            warning += ("\n\n⚠ %d من الموارد فيها سكربتات لم تُدمج — راجع "
                        "fxmanifest يدويًا بعد الدمج." % stats["scripts"])

        if not ask(self, "دمج الموارد",
                   "سيُنشأ مورد باسم «%s» فيه %d ملف بحجم %s.%s\n\nهل تتابع؟"
                   % (name, stats["files"], _size(stats["bytes"]), warning),
                   "ادمج", warning=bool(warning)):
            return

        progress = QProgressDialog("جاري الدمج…", "إلغاء", 0,
                                   stats["files"], self)
        progress.setWindowTitle("دمج الموارد")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        def step(index, total, filename):
            progress.setMaximum(total)
            progress.setValue(index)
            if index % 25 == 0:
                progress.setLabelText(filename)
                QApplication.processEvents()
            return not progress.wasCanceled()

        path, copied, failed = merge.apply(
            self.plan, out, name, step, moving, theme.AUTHOR)
        progress.close()

        show_info(self, "تمّ الدمج",
                  "أُنشئ المورد في:\n%s\n\nنُقل %d ملف%s.\n\n"
                  "أضف اسم المورد إلى server.cfg ثم أعد تشغيل السيرفر."
                  % (path, copied,
                     "، وفشل %d" % len(failed) if failed else ""),
                  "\n".join("%s: %s" % (n, e) for n, e in failed[:60])
                  if failed else None)
        self.statusMessage.emit("دُمج %d ملف في %s" % (copied, name))
