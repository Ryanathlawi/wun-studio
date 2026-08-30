"""
أداة مدقّق الملابس.

تمسح مورد ملابس، تعرض مشاكله مصنّفة، وتطبّق الإصلاحات المختارة فقط. كل شيء
يبدأ بمعاينة جافة، ولا يُكتب على القرص إلا بعد تأكيد صريح.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..core import clothing
from . import icons, theme
from .properties import _button
from .widgets import Divider, EmptyState

ISSUE_ROLE = Qt.UserRole + 1

KIND_LABELS = {
    "missing_texture": "قطع بلا تكستشر",
    "orphan_texture": "تكستشرات بلا قطعة",
    "drawable_gap": "فجوات في ترقيم القطع",
    "variant_gap": "فجوات في حروف التنويعات",
    "bad_name": "ملفات خارج نمط التسمية",
}

SEVERITY_ICON = {"error": ("warn", theme.DANGER),
                 "warning": ("warn", theme.WARN),
                 "info": ("info", theme.TXT_DIM)}


class ClothingTool(QWidget):
    """واجهة فحص وإصلاح موارد الملابس."""

    statusMessage = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder = None
        self.index = None
        self.issues = []

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

        self.btn_pick = _button("اختر مجلد الملابس", "open", "primary",
                                "مجلد stream داخل مورد الملابس")
        self.btn_pick.clicked.connect(self.pick_folder)
        row.addWidget(self.btn_pick)

        self.btn_rescan = _button("إعادة الفحص", "revert")
        self.btn_rescan.clicked.connect(self.rescan)
        self.btn_rescan.setEnabled(False)
        row.addWidget(self.btn_rescan)

        row.addWidget(Divider(vertical=True))

        self.path_field = QLineEdit()
        self.path_field.setReadOnly(True)
        self.path_field.setPlaceholderText("لم يُختر مجلد بعد")
        self.path_field.setLayoutDirection(Qt.LeftToRight)
        row.addWidget(self.path_field, 1)
        return bar

    def _build_body(self):
        host = QWidget()
        host.setObjectName("Panel")
        column = QVBoxLayout(host)
        column.setContentsMargins(10, 10, 10, 10)
        column.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(7)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("select", 15, theme.TXT_DIM))
        title = QLabel("نتيجة الفحص")
        title.setObjectName("PanelTitle")
        self.stats_label = QLabel("")
        self.stats_label.setObjectName("Hint")
        head.addWidget(glyph)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.stats_label)
        column.addLayout(head)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        self.tree.setIndentation(18)
        self.tree.setUniformRowHeights(False)
        self.tree.itemChanged.connect(self._on_item_changed)
        column.addWidget(self.tree, 1)

        self.empty = EmptyState(
            "select", "لم يُفحص أي مورد بعد",
            "اختر مجلد stream داخل مورد الملابس، وسيُفحص كل ما فيه من "
            "ملفات ydd و ytd بحثًا عن اليتامى والفجوات.")
        column.addWidget(self.empty, 1)
        self.tree.hide()
        return host

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

        self.btn_all = _button("تحديد كل القابل للإصلاح", "check")
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        self.btn_none = _button("إلغاء التحديد", "close")
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        self.btn_preview = _button("معاينة جافة", "info")
        self.btn_preview.clicked.connect(self.preview)
        self.btn_apply = _button("تطبيق الإصلاحات", "check", "primary")
        self.btn_apply.clicked.connect(self.apply_fixes)

        for widget in (self.btn_all, self.btn_none, self.btn_preview,
                       self.btn_apply):
            widget.setEnabled(False)
            row.addWidget(widget)
        return bar

    # ---------------------------------------------------------------- الفحص

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "اختر مجلد الملابس (‏stream)")
        if folder:
            self.folder = folder
            self.path_field.setText(folder)
            self.rescan()

    def rescan(self):
        if not self.folder:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.index = clothing.scan(self.folder)
            self.issues = clothing.diagnose(self.index)
        finally:
            QApplication.restoreOverrideCursor()

        stats = self.index.stats()
        self.stats_label.setText(
            "%d ملف · %d موديل · %d قطعة · %d تكستشر"
            % (stats["files"], stats["models"], stats["ydd"], stats["ytd"]))
        self._populate()
        self.btn_rescan.setEnabled(True)
        self.statusMessage.emit(
            "فُحص %s — %d مشكلة" % (os.path.basename(self.folder),
                                    len(self.issues)))

    def _populate(self):
        self.tree.blockSignals(True)
        self.tree.clear()

        grouped = {}
        for issue in self.issues:
            grouped.setdefault(issue.kind, []).append(issue)

        for kind, group in sorted(
                grouped.items(),
                key=lambda kv: clothing.SEVERITY_ORDER[kv[1][0].severity]):
            parent = QTreeWidgetItem(self.tree)
            fixable = sum(1 for issue in group if issue.fixable)
            parent.setText(0, "%s — %d (قابل للإصلاح: %d)"
                           % (KIND_LABELS.get(kind, kind), len(group), fixable))
            parent.setFont(0, theme.font(10, medium=True))
            name, colour = SEVERITY_ICON[group[0].severity]
            parent.setIcon(0, icons.icon(name, 15, colour))
            parent.setExpanded(kind in ("missing_texture", "drawable_gap"))

            for issue in group:
                child = QTreeWidgetItem(parent)
                child.setText(0, issue.title)
                child.setToolTip(0, issue.detail)
                child.setData(0, ISSUE_ROLE, issue)
                if issue.fixable:
                    child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                    child.setCheckState(0, Qt.Checked)
                    child.setText(0, "%s   ←   %s"
                                  % (issue.title, issue.fix.description))
                else:
                    child.setFlags(child.flags() & ~Qt.ItemIsUserCheckable)
                    child.setForeground(0, theme.color("TXT_MUTE"))

        self.tree.blockSignals(False)

        has_issues = bool(self.issues)
        self.tree.setVisible(has_issues)
        self.empty.setVisible(not has_issues)
        if not has_issues:
            self.empty.title.setText("المورد سليم")
            self.empty.hint.setText(
                "لم يُعثر على يتامى ولا فجوات في التسمية أو الترقيم.")
        for widget in (self.btn_all, self.btn_none, self.btn_preview,
                       self.btn_apply):
            widget.setEnabled(has_issues)
        self._refresh_summary()

    # --------------------------------------------------------------- التحديد

    def _iter_children(self):
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                yield parent.child(j)

    def _set_all(self, checked):
        self.tree.blockSignals(True)
        for child in self._iter_children():
            if child.flags() & Qt.ItemIsUserCheckable:
                child.setCheckState(0, Qt.Checked if checked else Qt.Unchecked)
        self.tree.blockSignals(False)
        self._refresh_summary()

    def _on_item_changed(self, _item, _column):
        self._refresh_summary()

    def selected_issues(self):
        chosen = []
        for child in self._iter_children():
            if not (child.flags() & Qt.ItemIsUserCheckable):
                continue
            if child.checkState(0) == Qt.Checked:
                issue = child.data(0, ISSUE_ROLE)
                if issue is not None:
                    chosen.append(issue)
        return chosen

    def _refresh_summary(self):
        chosen = self.selected_issues()
        actions = clothing.plan(chosen)
        counts = clothing.summary(self.issues)
        self.summary_label.setText(
            "أخطاء %d · تحذيرات %d · مختار %d مشكلة (%d عملية ملف)"
            % (counts["error"], counts["warning"], len(chosen), len(actions)))
        self.btn_apply.setEnabled(bool(actions))
        self.btn_preview.setEnabled(bool(actions))

    # -------------------------------------------------------------- التطبيق

    def preview(self):
        from .main_window import show_info
        actions = clothing.plan(self.selected_issues())
        kinds = {}
        for kind, _source, _target in actions:
            kinds[kind] = kinds.get(kind, 0) + 1
        labels = {"copy": "نسخ", "move": "نقل", "rename": "إعادة تسمية"}
        breakdown = "، ".join("%s %d" % (labels.get(k, k), n)
                              for k, n in sorted(kinds.items()))
        detail = "\n".join(
            "%s\n   %s  ←  %s" % (labels.get(k, k),
                                  os.path.basename(t), os.path.basename(s))
            for k, s, t in actions[:200])
        show_info(self, "معاينة جافة",
                  "ستُنفَّذ %d عملية على الملفات: %s.\n\n"
                  "لم يُكتب أي شيء بعد." % (len(actions), breakdown),
                  detail)

    def apply_fixes(self):
        from .main_window import ask, show_info
        chosen = self.selected_issues()
        actions = clothing.plan(chosen)
        if not actions:
            return

        renames = sum(1 for kind, _s, _t in actions if kind == "rename")
        warning = ""
        if renames:
            warning = ("\n\n⚠ من بينها %d عملية إعادة ترقيم. لو كانت أرقام "
                       "القطع مذكورة في ملفات meta أو في سكربتاتك فستحتاج "
                       "تحديثها يدويًا." % renames)

        if not ask(self, "تطبيق الإصلاحات",
                   "ستُنفَّذ %d عملية على ملفات المورد، ولا يمكن التراجع "
                   "تلقائيًا.%s\n\nهل أخذت نسخة احتياطية؟"
                   % (len(actions), warning),
                   "طبّق الآن", warning=True):
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            done, failed = clothing.apply(actions, dry_run=False)
        finally:
            QApplication.restoreOverrideCursor()

        show_info(self, "تمّ الإصلاح",
                  "نُفِّذت %d عملية بنجاح%s."
                  % (len(done), "، وفشلت %d" % len(failed) if failed else ""),
                  "\n".join("%s: %s" % (os.path.basename(p), e)
                            for p, e in failed) if failed else None)
        self.statusMessage.emit("أُصلحت %d عملية" % len(done))
        self.rescan()
