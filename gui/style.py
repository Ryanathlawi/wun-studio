"""Dark theme for the whole application."""

ACCENT = "#4da6ff"

DARK_QSS = """
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 12px; }

QWidget { background: #1e1f22; color: #d6d8dd; }

QMainWindow::separator { background: #2b2d31; width: 1px; height: 1px; }

QToolBar {
    background: #26282c;
    border: none;
    border-bottom: 1px solid #34363b;
    padding: 6px 8px;
    spacing: 4px;
}
QToolBar QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 10px;
    color: #d6d8dd;
}
QToolBar QToolButton:hover { background: #33363c; border-color: #3d4046; }
QToolBar QToolButton:pressed { background: #3c4048; }
QToolBar QToolButton:disabled { color: #6a6d74; }
QToolBar QToolButton:checked { background: #2f5d8c; border-color: #4da6ff; }
QToolBar::separator { background: #3a3d43; width: 1px; margin: 4px 6px; }

QDockWidget {
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
    color: #b9bcc2;
    font-weight: 600;
}
QDockWidget::title {
    background: #26282c;
    padding: 7px 10px;
    border-bottom: 1px solid #34363b;
}

QListWidget {
    background: #232427;
    border: none;
    outline: none;
    padding: 4px;
}
QListWidget::item {
    border-radius: 6px;
    padding: 4px;
    margin: 2px 2px;
    color: #c8cad0;
}
QListWidget::item:hover { background: #2c2f34; }
QListWidget::item:selected { background: #2f5d8c; color: #ffffff; }

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
    background: #2a2c30;
    border: 1px solid #3a3d43;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: #4da6ff;
    selection-color: #10161d;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
    border-color: #4da6ff;
}
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background: #2a2c30;
    border: 1px solid #3a3d43;
    selection-background-color: #2f5d8c;
    outline: none;
}

QPushButton {
    background: #313439;
    border: 1px solid #3d4046;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e2e4e9;
}
QPushButton:hover { background: #3a3e44; }
QPushButton:pressed { background: #2b2e33; }
QPushButton:disabled { color: #6a6d74; background: #2a2c30; }
QPushButton[accent="true"] {
    background: #2f6fb5; border-color: #4da6ff; color: #ffffff; font-weight: 600;
}
QPushButton[accent="true"]:hover { background: #3780cf; }
QPushButton[danger="true"]:hover { background: #7a3030; border-color: #b45252; }

QToolButton {
    background: #2a2c30;
    border: 1px solid #3a3d43;
    border-radius: 6px;
    padding: 6px;
    color: #d6d8dd;
}
QToolButton:hover { background: #33363c; }
QToolButton:checked { background: #2f5d8c; border-color: #4da6ff; color: #fff; }

QSlider::groove:horizontal {
    height: 4px; background: #3a3d43; border-radius: 2px;
}
QSlider::sub-page:horizontal { background: #4da6ff; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #e6e8ec; width: 13px; height: 13px;
    margin: -5px 0; border-radius: 7px;
}
QSlider::handle:horizontal:hover { background: #ffffff; }

QGroupBox {
    border: 1px solid #34363b;
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
    color: #9fa3ab;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QCheckBox { spacing: 7px; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1px solid #4a4d54; border-radius: 4px; background: #2a2c30;
}
QCheckBox::indicator:checked { background: #4da6ff; border-color: #4da6ff; }

QStatusBar { background: #26282c; border-top: 1px solid #34363b; color: #9fa3ab; }
QStatusBar::item { border: none; }

QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
QScrollBar::handle:vertical { background: #43464d; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #53565e; }
QScrollBar:horizontal { background: transparent; height: 11px; margin: 2px; }
QScrollBar::handle:horizontal { background: #43464d; border-radius: 5px; min-width: 28px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QMenu { background: #26282c; border: 1px solid #3a3d43; padding: 5px; }
QMenu::item { padding: 6px 22px; border-radius: 5px; }
QMenu::item:selected { background: #2f5d8c; }
QMenu::separator { height: 1px; background: #3a3d43; margin: 4px 8px; }

QMessageBox { background: #26282c; }
QProgressDialog { background: #26282c; }
QProgressBar {
    border: 1px solid #3a3d43; border-radius: 6px;
    background: #2a2c30; text-align: center; height: 16px;
}
QProgressBar::chunk { background: #4da6ff; border-radius: 5px; }

QLabel[hint="true"] { color: #8b8f97; }
QLabel[title="true"] { color: #e6e8ec; font-weight: 600; }
"""
