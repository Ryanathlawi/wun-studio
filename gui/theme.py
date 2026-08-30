"""
نظام التصميم: الألوان، الخطوط، والأبعاد، ثم بناء ورقة الأنماط.

كل قيمة لونية أو مقاس في الواجهة يبدأ من هنا، فلتغيير مزاج الواجهة كاملة
يكفي تعديل الثوابت في الأعلى دون لمس أي ملف آخر.
"""

from __future__ import annotations

from ..i18n import t

import glob
import os
import sys

from PySide6.QtGui import QColor, QFont, QFontDatabase

# ---------------------------------------------------------------- الهوية

APP_NAME = "Wun Studio"
APP_TAGLINE = t("محرّر تكستشرات GTA V و FiveM")
AUTHOR = "Athlawi"
VERSION = "1.3"
COPYRIGHT = "© 2026 Athlawi"
REPO = "Ryanathlawi/wun-studio"

# ---------------------------------------------------------------- الألوان

# مستمدّة من شعار Wun: سماوي فاتح، أزرق متوسط، وكحلي عميق
BG_APP = "#070B12"          # خلفية النافذة الخارجية
BG_PANEL = "#0E1826"        # اللوحات الجانبية
BG_ELEV = "#152238"         # البطاقات والعناصر المرتفعة
BG_INPUT = "#16233A"        # الحقول القابلة للكتابة
BG_HOVER = "#1B2C47"        # التحويم
BG_CANVAS = "#05080E"       # خلفية منطقة الرسم

BORDER = "#1F3352"
BORDER_HI = "#2E4E78"
CONTOUR = "#2E5C93"         # خطوط نقشة الخلفية

TXT = "#E8F0FA"             # النص الأساسي
TXT_DIM = "#8FA6C4"         # النص الثانوي
TXT_MUTE = "#5A7091"        # التلميحات

ACCENT = "#29A9E2"          # سماوي الشعار
ACCENT_HI = "#5FC6F5"       # سماوي فاتح للتحويم
ACCENT_MID = "#1C7FC4"      # أزرق متوسط
ACCENT_DEEP = "#0E3A6B"     # كحلي عميق

OK = "#35C08A"
WARN = "#E8A33D"
DANGER = "#E5484D"

# ---------------------------------------------------------------- الأبعاد

R_PANEL = 10                # نصف قطر زوايا اللوحات
R_CTRL = 7                  # نصف قطر زوايا عناصر التحكم
RAIL_W = 54                 # عرض ريل الأدوات
TITLEBAR_H = 42
RESIZE_EDGE = 6             # سماكة حافة تغيير حجم النافذة

def _assets_dir() -> str:
    """
    مسار مجلد الخطوط.

    عند التشغيل من المصدر يكون بجوار الحزمة. وعند التشغيل من ملف exe مبنيّ
    بـ PyInstaller تُفكّ الموارد إلى مجلد مؤقّت يشير إليه sys._MEIPASS، فنجرّبه
    أولًا ثم نرجع للمسار العادي.
    """
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        packed = os.path.join(bundle, os.path.basename(package_root),
                              "assets", "fonts")
        if os.path.isdir(packed):
            return packed
        packed = os.path.join(bundle, "assets", "fonts")
        if os.path.isdir(packed):
            return packed
    return os.path.join(package_root, "assets", "fonts")


_ASSETS = _assets_dir()

# اسم عائلة الخط بعد التحميل - يُملأ في load_fonts()
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MED = "Segoe UI"
_FALLBACKS = ("Segoe UI", "Tahoma", "Arial")


def load_fonts() -> str:
    """
    تحميل خطوط المشروع.

    يبحث أولًا في assets/fonts داخل المشروع، ثم في الخطوط المثبّتة على النظام،
    فيشتغل الخط سواء ثبّته المستخدم في ويندوز أو رمى ملفاته في المجلد. وإن لم
    يوجد أصلًا ترجع الواجهة إلى خط النظام بدل أن تنهار.
    """
    global FONT_FAMILY, FONT_FAMILY_MED

    loaded = []
    for path in sorted(glob.glob(os.path.join(_ASSETS, "*.ttf")) +
                       glob.glob(os.path.join(_ASSETS, "*.otf"))):
        fid = QFontDatabase.addApplicationFont(path)
        if fid != -1:
            loaded += QFontDatabase.applicationFontFamilies(fid)

    available = set(QFontDatabase.families())
    candidates = loaded + [f for f in available if "thmanyah" in f.lower()]

    base = next((f for f in candidates if f.lower() == "thmanyah sans"), None)
    if base is None:
        base = next((f for f in candidates
                     if "thmanyah" in f.lower() and "med" not in f.lower()), None)
    med = next((f for f in candidates if "med" in f.lower()), None)

    if base is None:
        base = next((f for f in _FALLBACKS if f in available), "Segoe UI")
    FONT_FAMILY = base
    FONT_FAMILY_MED = med or base
    return FONT_FAMILY


def font(size=10, weight=QFont.Normal, medium=False) -> QFont:
    """خط الواجهة بالمقاس والوزن المطلوبين."""
    f = QFont(FONT_FAMILY_MED if medium else FONT_FAMILY)
    f.setPointSize(size)
    f.setWeight(weight)
    return f


def color(name: str) -> QColor:
    """لون من رموز التصميم بالاسم."""
    return QColor(globals()[name])


def apply_palette(app) -> None:
    """
    فرض لوحة ألوان داكنة على مستوى التطبيق.

    ورقة الأنماط وحدها لا تكفي: أي عنصر لا يطابقه محدِّد فيها - مثل منفذ
    العرض داخل منطقة التمرير، أو حوارات النظام - يرسم بلوحة النظام الفاتحة،
    فيصير نص فاتح على خلفية فاتحة. ضبط اللوحة يغطي هذه الحالات كلها.
    """
    from PySide6.QtGui import QPalette

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(BG_PANEL))
    pal.setColor(QPalette.WindowText, QColor(TXT))
    pal.setColor(QPalette.Base, QColor(BG_INPUT))
    pal.setColor(QPalette.AlternateBase, QColor(BG_ELEV))
    pal.setColor(QPalette.Text, QColor(TXT))
    pal.setColor(QPalette.PlaceholderText, QColor(TXT_MUTE))
    pal.setColor(QPalette.Button, QColor(BG_ELEV))
    pal.setColor(QPalette.ButtonText, QColor(TXT))
    pal.setColor(QPalette.BrightText, QColor("#FFFFFF"))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    pal.setColor(QPalette.ToolTipBase, QColor(BG_ELEV))
    pal.setColor(QPalette.ToolTipText, QColor(TXT))
    pal.setColor(QPalette.Link, QColor(ACCENT))

    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(TXT_MUTE))
    pal.setColor(QPalette.Disabled, QPalette.Base, QColor(BG_PANEL))
    pal.setColor(QPalette.Disabled, QPalette.Button, QColor(BG_PANEL))

    app.setPalette(pal)


# ------------------------------------------------------------ ورقة الأنماط

_QSS = """
* { outline: none; }

QWidget {
    color: @TXT;
    font-family: "@FONT";
    font-size: 10pt;
}

QToolTip {
    background: @BG_ELEV;
    color: @TXT;
    border: 1px solid @BORDER_HI;
    border-radius: 6px;
    padding: 6px 9px;
}

/* ---------- الأسطح ---------- */

#Shell      { background: @BG_APP; border: 1px solid @BORDER_HI;
              border-radius: @R_PANEL; }
#TitleBar   { background: transparent; }
#Panel      { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                          stop:0 #16253C, stop:0.18 @BG_PANEL,
                          stop:1 @BG_PANEL);
              border: 1px solid @BORDER; border-radius: @R_PANEL; }
#Rail       { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                          stop:0 #16253C, stop:0.25 @BG_PANEL,
                          stop:1 @BG_PANEL);
              border: 1px solid @BORDER; border-radius: @R_PANEL; }
#SectionBody { background: transparent; }
#CanvasHost { background: @BG_CANVAS; border: 1px solid @BORDER;
              border-radius: @R_PANEL; }
#StatusBar  { background: transparent; }

#PanelTitle { color: @TXT_DIM; font-size: 9pt;
              letter-spacing: 0.5px; }
#Hint       { color: @TXT_MUTE; font-size: 9pt; }
#Value      { color: @TXT_DIM; font-size: 9pt; }

/* ---------- الأزرار ---------- */

QPushButton {
    background: @BG_ELEV;
    border: 1px solid @BORDER;
    border-radius: @R_CTRL;
    padding: 7px 12px;
    color: @TXT;
}
QPushButton:hover    { background: @BG_HOVER; border-color: @BORDER_HI; }
QPushButton:pressed  { background: @BG_INPUT; }
QPushButton:disabled { color: @TXT_MUTE; background: @BG_PANEL;
                       border-color: @BORDER; }

QPushButton[kind="primary"] {
    background: @ACCENT; border-color: @ACCENT; color: #FFFFFF;
}
QPushButton[kind="primary"]:hover    { background: @ACCENT_HI;
                                       border-color: @ACCENT_HI; }
QPushButton[kind="primary"]:pressed  { background: @ACCENT_DEEP; }
QPushButton[kind="primary"]:disabled { background: @ACCENT_DEEP;
                                       border-color: @ACCENT_DEEP;
                                       color: #9DB4D8; }

QPushButton[kind="danger"]       { color: @DANGER; }
QPushButton[kind="danger"]:hover { background: #2A1B1E; border-color: @DANGER; }

QPushButton[kind="ghost"] {
    background: transparent; border-color: transparent; color: @TXT_DIM;
}
QPushButton[kind="ghost"]:hover { background: @BG_HOVER; color: @TXT; }

/* ---------- الحقول ---------- */

QLineEdit, QPlainTextEdit, QSpinBox, QComboBox, QFontComboBox {
    background: @BG_INPUT;
    border: 1px solid @BORDER;
    border-radius: @R_CTRL;
    padding: 6px 9px;
    selection-background-color: @ACCENT;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
QComboBox:focus, QFontComboBox:focus { border-color: @ACCENT; }
QLineEdit:disabled, QSpinBox:disabled, QPlainTextEdit:disabled,
QComboBox:disabled { color: @TXT_MUTE; background: @BG_PANEL; }

QSpinBox::up-button, QSpinBox::down-button { width: 0; border: none; }

QComboBox::drop-down, QFontComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView, QFontComboBox QAbstractItemView {
    background: @BG_ELEV;
    border: 1px solid @BORDER_HI;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: @ACCENT_DEEP;
    outline: none;
}

/* ---------- المنزلقات ---------- */

QSlider::groove:horizontal {
    height: 4px; background: @BG_INPUT; border-radius: 2px;
}
QSlider::sub-page:horizontal { background: @ACCENT; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #FFFFFF; width: 13px; height: 13px;
    margin: -5px 0; border-radius: 7px;
}
QSlider::handle:horizontal:hover     { background: @ACCENT_HI; }
QSlider::groove:horizontal:disabled  { background: @BG_PANEL; }
QSlider::sub-page:horizontal:disabled { background: @BORDER_HI; }
QSlider::handle:horizontal:disabled  { background: @TXT_MUTE; }

/* ---------- صناديق الاختيار ---------- */

QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid @BORDER_HI; border-radius: 5px; background: @BG_INPUT;
}
QCheckBox::indicator:hover    { border-color: @ACCENT; }
QCheckBox::indicator:checked  { background: @ACCENT; border-color: @ACCENT; }
QCheckBox::indicator:disabled { background: @BG_PANEL; border-color: @BORDER; }

/* ---------- القوائم وأشرطة التمرير ---------- */

QListView, QListWidget { background: transparent; border: none; outline: none; }
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
    background: transparent; border: none;
}

QScrollBar:vertical   { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: @BORDER_HI; border-radius: 4px;
    min-height: 30px; min-width: 30px;
}
QScrollBar::handle:hover { background: @TXT_MUTE; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---------- الشاشة الرئيسية والشجرة ---------- */

#Home { background: transparent; }

QTreeWidget {
    background: transparent;
    border: none;
    outline: none;
}
QTreeWidget::item {
    padding: 6px 4px;
    border-radius: 6px;
}
QTreeWidget::item:hover    { background: @BG_HOVER; }
QTreeWidget::item:selected { background: @ACCENT_DEEP; color: @TXT; }

/* شجرة الملفات: شريط تحديد متصل. منطقة الفرع خارج مستطيل العنصر، فلو بقيت
   بلا لون ظهرت فجوة قبل الشريط. المجلدات غير قابلة للاختيار فلا تُمسّ أسهمها. */
#FileTree::item { border-radius: 0px; }
#FileTree::branch:selected { background: @ACCENT_DEEP; }
QTreeWidget::indicator {
    width: 15px; height: 15px;
    border: 1px solid @BORDER_HI; border-radius: 4px; background: @BG_INPUT;
}
QTreeWidget::indicator:checked {
    background: @ACCENT; border-color: @ACCENT;
}

/* ---------- المقسّمات ---------- */

QSplitter::handle           { background: transparent; }
QSplitter::handle:horizontal { width: 9px; }
QSplitter::handle:vertical   { height: 9px; }
QSplitter::handle:hover      { background: @ACCENT_DEEP; border-radius: 4px; }

/* ---------- الحوارات ---------- */

QDialog, QMessageBox   { background: @BG_PANEL; }
QMessageBox QLabel     { color: @TXT; }
QProgressDialog        { background: @BG_PANEL; }
QProgressBar {
    background: @BG_INPUT; border: none; border-radius: 4px;
    height: 6px; text-align: center; color: transparent;
}
QProgressBar::chunk { background: @ACCENT; border-radius: 4px; }
"""


def qss() -> str:
    """ورقة الأنماط بعد استبدال رموز التصميم بقيمها."""
    tokens = {
        "@FONT": FONT_FAMILY,
        "@R_PANEL": "%dpx" % R_PANEL,
        "@R_CTRL": "%dpx" % R_CTRL,
    }
    # الأطول أولًا حتى لا يبتلع BORDER الرمزَ BORDER_HI
    for key in ("BG_APP", "BG_PANEL", "BG_ELEV", "BG_INPUT", "BG_HOVER",
                "BG_CANVAS", "BORDER_HI", "BORDER", "CONTOUR", "TXT_DIM",
                "TXT_MUTE", "TXT", "ACCENT_HI", "ACCENT_MID", "ACCENT_DEEP",
                "ACCENT", "OK", "WARN", "DANGER"):
        tokens["@" + key] = globals()[key]

    out = _QSS
    for key, value in tokens.items():
        out = out.replace(key, value)
    return out
