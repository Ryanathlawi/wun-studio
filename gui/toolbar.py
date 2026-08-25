"""Top toolbar: file actions, history, tool selection and zoom controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QLabel, QSizePolicy, QToolBar, QWidget

from . import canvas as cv

TOOLS = [
    (cv.TOOL_BRUSH, "Brush", "B", "Paint with the current colour"),
    (cv.TOOL_ERASER, "Eraser", "E", "Erase to transparency"),
    (cv.TOOL_TEXT, "Text", "T", "Click on the canvas to place text"),
    (cv.TOOL_RECT, "Rect", "R", "Drag to draw a rectangle"),
    (cv.TOOL_ELLIPSE, "Ellipse", "L", "Drag to draw an ellipse"),
    (cv.TOOL_LINE, "Line", "N", "Drag to draw a straight line"),
    (cv.TOOL_PICK, "Pick", "I", "Pick a colour from the texture"),
]


class EditorToolBar(QToolBar):
    """The application's single top toolbar."""

    toolChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__("Main", parent)
        self.setMovable(False)
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)

        # --- file ---------------------------------------------------------
        self.act_open = QAction("Open YTD", self)
        self.act_open.setShortcut("Ctrl+O")
        self.act_open.setToolTip("Open a .ytd texture dictionary (Ctrl+O)")

        self.act_save_as = QAction("Save As YTD", self)
        self.act_save_as.setShortcut("Ctrl+Shift+S")
        self.act_save_as.setToolTip("Write a new .ytd with your edits (Ctrl+Shift+S)")
        self.act_save_as.setEnabled(False)

        self.addAction(self.act_open)
        self.addAction(self.act_save_as)
        self.addSeparator()

        # --- history ------------------------------------------------------
        self.act_undo = QAction("Undo", self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.setEnabled(False)

        self.act_redo = QAction("Redo", self)
        self.act_redo.setShortcut("Ctrl+Y")
        self.act_redo.setEnabled(False)

        self.addAction(self.act_undo)
        self.addAction(self.act_redo)
        self.addSeparator()

        # --- tools --------------------------------------------------------
        self.tool_actions = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        for key, label, shortcut, tip in TOOLS:
            act = QAction(label, self)
            act.setCheckable(True)
            act.setShortcut(shortcut)
            act.setToolTip("%s (%s)" % (tip, shortcut))
            act.triggered.connect(lambda _checked, k=key: self.toolChanged.emit(k))
            group.addAction(act)
            self.addAction(act)
            self.tool_actions[key] = act
        self.tool_actions[cv.TOOL_BRUSH].setChecked(True)
        self.addSeparator()

        # --- zoom ---------------------------------------------------------
        self.act_zoom_out = QAction("Zoom -", self)
        self.act_zoom_out.setShortcut("Ctrl+-")
        self.act_zoom_in = QAction("Zoom +", self)
        self.act_zoom_in.setShortcut("Ctrl+=")
        self.act_zoom_fit = QAction("Fit", self)
        self.act_zoom_fit.setShortcut("Ctrl+0")
        self.act_zoom_reset = QAction("100%", self)
        self.act_zoom_reset.setShortcut("Ctrl+1")

        self.addAction(self.act_zoom_out)
        self.addAction(self.act_zoom_in)
        self.addAction(self.act_zoom_fit)
        self.addAction(self.act_zoom_reset)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.addWidget(spacer)

        self.file_label = QLabel("No file loaded")
        self.file_label.setProperty("hint", True)
        self.file_label.setContentsMargins(10, 0, 10, 0)
        self.addWidget(self.file_label)

    def set_tool(self, key):
        act = self.tool_actions.get(key)
        if act is not None:
            act.setChecked(True)

    def set_file_label(self, text):
        self.file_label.setText(text)
