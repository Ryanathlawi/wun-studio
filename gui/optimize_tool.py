"""
أداة ضغط الموارد.

تمسح مورد FiveM كاملًا (ملابس، سيارات، خرائط)، تحسب كم يمكن توفيره بتصغير
التكستشرات المبالغ فيها وتحويل الصيغ التي لا تستعمل قناة الشفافية، ثم تكتب
نسخة محسّنة في مجلد جديد. المورد الأصلي لا يُلمس إطلاقًا.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QProgressDialog, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..core import optimize as opt
from . import icons, theme
from .properties import _button
from .widgets import Divider, EmptyState, SliderField


def _mb(value):
    return "%.1f م.ب" % (value / 1e6)


class OptimizeTool(QWidget):
    """واجهة فحص وضغط موارد FiveM."""

    statusMessage = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder = None
        self.plans = []

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

        self.btn_pick = _button("اختر مجلد المورد", "open", "primary",
                                "مجلد stream داخل المورد")
        self.btn_pick.clicked.connect(self.pick_folder)
        row.addWidget(self.btn_pick)

        self.preset = QComboBox()
        self.preset.setFixedHeight(34)
        for key, data in opt.PRESETS.items():
            cap = data["max_size"]
            label = "%s — سقف %s" % (data["label"],
                                     "%d px" % cap if cap else "بلا تصغير")
            self.preset.addItem(label, key)
        self.preset.currentIndexChanged.connect(self._on_preset)
        row.addWidget(self.preset)

        self.cap = SliderField("سقف الأبعاد", 0, 4096, 1024, " بكسل")
        self.cap.setFixedWidth(210)
        self.cap.valueChanged.connect(lambda _v: None)
        row.addWidget(self.cap)

        self.btn_scan = _button("افحص", "search")
        self.btn_scan.clicked.connect(self.rescan)
        self.btn_scan.setEnabled(False)
        row.addWidget(self.btn_scan)

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
        glyph.setPixmap(icons.pixmap("batch", 15, theme.TXT_DIM))
        title = QLabel("تقرير الضغط")
        title.setObjectName("PanelTitle")
        self.stats_label = QLabel("")
        self.stats_label.setObjectName("Hint")
        head.addWidget(glyph)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.stats_label)
        column.addLayout(head)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["الملف / التكستشر", "قبل", "بعد", "الإجراء"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for column_index in (1, 2, 3):
            self.tree.header().setSectionResizeMode(column_index,
                                                    QHeaderView.ResizeToContents)
        self.tree.setIndentation(16)
        column.addWidget(self.tree, 1)

        self.empty = EmptyState(
            "batch", "لم يُفحص أي مورد بعد",
            "اختر مجلد المورد ثم اضغط «افحص». لن يُكتب شيء — التقرير يوريك "
            "كم يمكن توفيره قبل أي قرار.")
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

        self.btn_apply = _button("اكتب نسخة محسّنة…", "export", "primary")
        self.btn_apply.clicked.connect(self.apply_optimisation)
        self.btn_apply.setEnabled(False)
        row.addWidget(self.btn_apply)
        return bar

    # -------------------------------------------------------------- الإعداد

    def _on_preset(self):
        key = self.preset.currentData()
        rules = opt.PRESETS.get(key, {})
        self.cap.slider.blockSignals(True)
        self.cap.setValue(rules.get("max_size", 1024))
        self.cap.slider.blockSignals(False)

    def rules(self):
        key = self.preset.currentData()
        base = dict(opt.PRESETS.get(key, opt.DEFAULT_RULES))
        base["max_size"] = self.cap.value()
        base.setdefault("opaque_to_dxt1", True)
        return base

    # ---------------------------------------------------------------- الفحص

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلد المورد")
        if folder:
            self.folder = folder
            self.path_field.setText(folder)
            self.btn_scan.setEnabled(True)
            self.rescan()

    def rescan(self):
        if not self.folder:
            return
        progress = QProgressDialog("جاري فحص الملفات…", "إلغاء", 0, 1, self)
        progress.setWindowTitle("فحص المورد")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(300)

        def step(index, total, path):
            progress.setMaximum(total)
            progress.setValue(index)
            progress.setLabelText(os.path.basename(path))
            QApplication.processEvents()
            return not progress.wasCanceled()

        self.plans = opt.scan(self.folder, self.rules(), step)
        progress.close()
        self._populate()

    def _populate(self):
        self.tree.clear()
        stats = opt.summary(self.plans)

        for file_plan in sorted(self.plans, key=lambda p: -p.saved):
            if file_plan.error:
                item = QTreeWidgetItem(self.tree)
                item.setText(0, file_plan.name)
                item.setText(3, "غير مقروء")
                item.setIcon(0, icons.icon("warn", 14, theme.DANGER))
                continue
            if not file_plan.changed:
                continue

            item = QTreeWidgetItem(self.tree)
            item.setText(0, file_plan.name)
            item.setText(1, _mb(file_plan.old_bytes))
            item.setText(2, _mb(file_plan.new_bytes))
            item.setText(3, "توفير %d%%" % round(
                100 * file_plan.saved / max(1, file_plan.old_bytes)))
            item.setFont(0, theme.font(10, medium=True))
            item.setIcon(0, icons.icon("layers", 14, theme.ACCENT))

            for texture in file_plan.textures:
                if not texture.changed:
                    continue
                child = QTreeWidgetItem(item)
                child.setText(0, "%s  (%d×%d → %d×%d)"
                              % (texture.name, texture.entry.width,
                                 texture.entry.height, texture.width,
                                 texture.height))
                child.setText(1, _mb(texture.old_bytes))
                child.setText(2, _mb(texture.new_bytes))
                child.setText(3, "، ".join(texture.reasons))

        has_savings = stats["changed"] > 0
        self.tree.setVisible(has_savings)
        self.empty.setVisible(not has_savings)
        if not has_savings:
            self.empty.title.setText("لا يوجد ما يُضغط")
            self.empty.hint.setText(
                "كل التكستشرات ضمن السقف المختار ولا توجد صيغ زائدة. "
                "جرّب سقفًا أصغر أو نمطًا أقوى.")

        self.stats_label.setText(
            "%d ملف · %d قابل للتحسين · %d غير مقروء"
            % (stats["files"], stats["changed"], stats["errors"]))
        percent = 100 * stats["saved"] / max(1, stats["old_bytes"])
        self.summary_label.setText(
            "بيانات البكسل %s ← %s   ·   التوفير %s (%.0f%%)   ·   "
            "%d تكستشر صُغّر، %d غيّر صيغته"
            % (_mb(stats["old_bytes"]), _mb(stats["new_bytes"]),
               _mb(stats["saved"]), percent, stats["downscaled"],
               stats["reformatted"]))
        self.btn_apply.setEnabled(has_savings)
        self.statusMessage.emit(
            "فُحص %s — توفير %s" % (os.path.basename(self.folder),
                                    _mb(stats["saved"])))

    # -------------------------------------------------------------- التنفيذ

    def apply_optimisation(self):
        from .main_window import ask, show_info

        out = QFileDialog.getExistingDirectory(
            self, "اختر مجلدًا للنسخة المحسّنة")
        if not out:
            return
        if os.path.abspath(out) == os.path.abspath(self.folder):
            show_info(self, "اختر مجلدًا آخر",
                      "لا يمكن الكتابة داخل المورد الأصلي. اختر مجلدًا فارغًا "
                      "حتى يبقى الأصل سليمًا.")
            return

        stats = opt.summary(self.plans)
        if not ask(self, "كتابة النسخة المحسّنة",
                   "ستُكتب %d ملف في:\n%s\n\nالتوفير المتوقع %s. الملفات غير "
                   "المتغيّرة تُنسخ كما هي، والمورد الأصلي لا يُلمس.\n\n"
                   "إعادة الترميز تستغرق وقتًا على الموارد الكبيرة. هل تتابع؟"
                   % (stats["files"], out, _mb(stats["saved"])), "ابدأ"):
            return

        progress = QProgressDialog("جاري إعادة الترميز…", "إلغاء", 0,
                                   len(self.plans), self)
        progress.setWindowTitle("ضغط المورد")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        def step(index, total, name):
            progress.setMaximum(total)
            progress.setValue(index)
            progress.setLabelText(name)
            QApplication.processEvents()
            return not progress.wasCanceled()

        written, skipped, failed = opt.apply(self.plans, self.folder, out, step)
        progress.close()

        before = sum(p.file_size for p in self.plans)
        after = 0
        for root, _dirs, names in os.walk(out):
            for name in names:
                after += os.path.getsize(os.path.join(root, name))

        show_info(
            self, "تمّت الكتابة",
            "كُتب %d ملف محسّن، ونُسخ %d كما هو%s.\n\n"
            "الحجم على القرص: %s ← %s (توفير %.0f%%)"
            % (len(written), len(skipped),
               "، وفشل %d" % len(failed) if failed else "",
               _mb(before), _mb(after),
               100 * (before - after) / max(1, before)),
            "\n".join("%s: %s" % (name, err) for name, err in failed[:60])
            if failed else None)
        self.statusMessage.emit("كُتبت نسخة محسّنة في %s" % out)
