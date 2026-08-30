"""
مثبّت Wun Studio.

يُبنى بـ PyInstaller في ملف واحد يحمل بداخله نسخة البرنامج مضغوطة، فيكفي
المستخدم تنزيل ملف واحد وتشغيله. يُنشئ اختصارات سطح المكتب وقائمة ابدأ،
ويسجّل البرنامج في «إضافة أو إزالة البرامج» ليُزال بالطريقة المعتادة.

    python -m PyInstaller build_tools/installer.spec --noconfirm
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile

APP_NAME = "Wun Studio"
PUBLISHER = "Athlawi"
VERSION = "1.3"
TAGLINE = "محرّر وأدوات GTA V و FiveM"
COPYRIGHT = "© 2026 Athlawi"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\WunStudio"
EXE_NAME = "Wun Studio.exe"
PAYLOAD = "payload.zip"

BG_APP = "#0D0E12"
BG_PANEL = "#14161B"
BG_ELEV = "#1B1E25"
BG_INPUT = "#21252E"
BORDER = "#282D38"
BORDER_HI = "#39404E"
TXT = "#E8EBF1"
TXT_DIM = "#98A2B2"
TXT_MUTE = "#5E6775"
ACCENT = "#4C8DFF"
ACCENT_HI = "#6FA5FF"
ACCENT_DEEP = "#23406E"
DANGER = "#E5484D"

QSS = """
QWidget { color: %(TXT)s; font-size: 10pt; background: transparent; }
#Shell { background: %(BG_APP)s; border: 1px solid %(BORDER_HI)s;
         border-radius: 10px; }
#Panel { background: %(BG_PANEL)s; border: 1px solid %(BORDER)s;
         border-radius: 10px; }
#Hint { color: %(TXT_MUTE)s; font-size: 9pt; }
#Title { font-size: 20pt; }
QPushButton { background: %(BG_ELEV)s; border: 1px solid %(BORDER)s;
              border-radius: 7px; padding: 9px 18px; }
QPushButton:hover { background: %(BG_INPUT)s; border-color: %(BORDER_HI)s; }
QPushButton[kind="primary"] { background: %(ACCENT)s; border-color: %(ACCENT)s;
                              color: #FFFFFF; }
QPushButton[kind="primary"]:hover { background: %(ACCENT_HI)s; }
QPushButton[kind="primary"]:disabled { background: %(ACCENT_DEEP)s;
                                       border-color: %(ACCENT_DEEP)s;
                                       color: #9DB4D8; }
QPushButton[kind="danger"] { color: %(DANGER)s; }
QLineEdit { background: %(BG_INPUT)s; border: 1px solid %(BORDER)s;
            border-radius: 7px; padding: 8px 10px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px;
                       border: 1px solid %(BORDER_HI)s; background: %(BG_INPUT)s; }
QCheckBox::indicator:checked { background: %(ACCENT)s; border-color: %(ACCENT)s; }
QProgressBar { background: %(BG_INPUT)s; border: none; border-radius: 4px;
               height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { background: %(ACCENT)s; border-radius: 4px; }
""" % globals()


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def default_target():
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(root, "Programs", APP_NAME)


def _powershell(script):
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return None


def make_shortcut(link_path, target, icon=None, arguments=""):
    """
    إنشاء اختصار ويندوز.

    المجلد يُنشأ داخل أمر PowerShell نفسه لا من بايثون: إنشاؤه من عملية ثم
    استدعاء COM من عملية أخرى يجعل الاختصار يفشل أحيانًا لأن المجلد لم يظهر
    بعد لتلك العملية.
    """
    folder = os.path.dirname(link_path)
    script = (
        "New-Item -ItemType Directory -Force -Path '%s' | Out-Null;"
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
        "$s.TargetPath = '%s';"
        "$s.WorkingDirectory = '%s';"
        "$s.Arguments = '%s';"
        "$s.IconLocation = '%s';"
        "$s.Description = '%s';"
        "$s.Save()"
        % (folder, link_path, target, os.path.dirname(target), arguments,
           icon or target, TAGLINE))

    for _attempt in range(3):
        _powershell(script)
        if os.path.exists(link_path):
            return True
    return os.path.exists(link_path)


def _known_folder(name, fallback):
    result = _powershell("[Environment]::GetFolderPath('%s')" % name)
    if result and result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return fallback


def start_menu_dir():
    root = os.environ.get("APPDATA") or os.path.expanduser("~")
    programs = _known_folder(
        "Programs",
        os.path.join(root, "Microsoft", "Windows", "Start Menu", "Programs"))
    return os.path.join(programs, APP_NAME)


def desktop_dir():
    return _known_folder("Desktop",
                         os.path.join(os.path.expanduser("~"), "Desktop"))


def register(target, size_kb):
    import winreg
    exe = os.path.join(target, EXE_NAME)
    uninstaller = os.path.join(target, "uninstall.exe")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
        for name, value in (
                ("DisplayName", APP_NAME),
                ("DisplayVersion", VERSION),
                ("Publisher", PUBLISHER),
                ("DisplayIcon", exe),
                ("InstallLocation", target),
                ("UninstallString", '"%s" --uninstall' % uninstaller),
                ("QuietUninstallString", '"%s" --uninstall --silent'
                 % uninstaller)):
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


def unregister():
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except OSError:
        pass


def installed_location():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
            return winreg.QueryValueEx(key, "InstallLocation")[0]
    except OSError:
        return None


def uninstall_mode():
    """
    هل هذه النسخة مزيل تثبيت؟

    المزيل نسخة من المثبّت نفسه، فلا يفرّقهما إلا الوسائط أو الاسم. الاعتماد
    على الوسائط وحدها يجعل النقر المزدوج على uninstall.exe يفتح شاشة تثبيت.
    """
    if "--uninstall" in sys.argv:
        return True
    return os.path.basename(sys.executable).lower().startswith("uninstall")


def schedule_removal(folder):
    """
    حذف مجلد التثبيت بعد خروج المزيل نفسه، فهو يعمل من داخله.

    يُطلق العلم CREATE_NO_WINDOW وحده. جمعه مع DETACHED_PROCESS ينتج عملية
    لا تنفّذ شيئًا، فيبقى المجلد كما هو دون رسالة خطأ.
    """
    script = (
        "$p=%d; while (Get-Process -Id $p -ErrorAction SilentlyContinue) "
        "{ Start-Sleep -Milliseconds 300 }; "
        "Start-Sleep -Milliseconds 700; "
        "for ($i=0; $i -lt 40; $i++) { "
        "Remove-Item -LiteralPath '%s' -Recurse -Force "
        "-ErrorAction SilentlyContinue; "
        "if (-not (Test-Path -LiteralPath '%s')) { break }; "
        "Start-Sleep -Milliseconds 500 }"
        % (os.getpid(), folder, folder))
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle",
             "Hidden", "-Command", script],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False


def payload_entries():
    with zipfile.ZipFile(resource(PAYLOAD)) as archive:
        return archive.infolist()


def extract_payload(target, progress=None):
    os.makedirs(target, exist_ok=True)
    with zipfile.ZipFile(resource(PAYLOAD)) as archive:
        members = archive.infolist()
        for index, member in enumerate(members):
            archive.extract(member, target)
            if progress is not None:
                progress(index + 1, len(members), member.filename)
    return sum(m.file_size for m in payload_entries())


def do_uninstall(remove_shortcuts=True):
    target = installed_location()
    if remove_shortcuts:
        for link in (os.path.join(desktop_dir(), APP_NAME + ".lnk"),
                     os.path.join(start_menu_dir(), APP_NAME + ".lnk"),
                     os.path.join(start_menu_dir(), "إزالة %s.lnk" % APP_NAME)):
            try:
                if os.path.exists(link):
                    os.remove(link)
            except OSError:
                pass
        try:
            folder = start_menu_dir()
            if os.path.isdir(folder) and not os.listdir(folder):
                os.rmdir(folder)
        except OSError:
            pass
    unregister()
    if target and os.path.isdir(target):
        schedule_removal(target)
    return target


# --------------------------------------------------------------------------
# الواجهة
# --------------------------------------------------------------------------

def run_gui():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFontDatabase, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import QByteArray, QRectF
    from PySide6.QtWidgets import (QApplication, QCheckBox, QFileDialog,
                                   QFrame, QHBoxLayout, QLabel, QLineEdit,
                                   QProgressBar, QPushButton, QVBoxLayout,
                                   QWidget)

    LOGO = ("M12 3 21 8l-9 5-9-5zM3 13l9 5 9-5")

    def logo_pixmap(size, colour=ACCENT, width=1.5):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
               'fill="none" stroke="%s" stroke-width="%s" '
               'stroke-linecap="round" stroke-linejoin="round">'
               '<path d="%s"/></svg>' % (colour, width, LOGO)).encode()
        renderer = QSvgRenderer(QByteArray(svg))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        return pixmap

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    family = "Segoe UI"
    for name in ("ThmanyahSans-Regular.ttf", "ThmanyahSans-Bold.ttf",
                 "ThmanyahSans-Medium.ttf"):
        path = resource(os.path.join("fonts", name))
        if os.path.exists(path):
            fid = QFontDatabase.addApplicationFont(path)
            if fid != -1:
                families = QFontDatabase.applicationFontFamilies(fid)
                if families:
                    family = families[0]
    font = app.font()
    font.setFamily(family)
    font.setPointSize(10)
    app.setFont(font)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setStyleSheet(QSS)

    uninstalling = uninstall_mode()

    window = QWidget()
    window.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
    window.setAttribute(Qt.WA_TranslucentBackground, True)
    window.setFixedSize(600, 430)
    window.setWindowTitle(APP_NAME)

    outer = QVBoxLayout(window)
    outer.setContentsMargins(10, 10, 10, 10)
    shell = QFrame()
    shell.setObjectName("Shell")
    outer.addWidget(shell)

    column = QVBoxLayout(shell)
    column.setContentsMargins(30, 26, 30, 22)
    column.setSpacing(12)

    top = QHBoxLayout()
    close = QPushButton("✕")
    close.setFixedSize(30, 28)
    close.clicked.connect(window.close)
    top.addWidget(close)
    top.addStretch(1)
    column.addLayout(top)

    mark = QLabel()
    mark.setPixmap(logo_pixmap(52))
    mark.setAlignment(Qt.AlignCenter)
    column.addWidget(mark)

    title = QLabel(APP_NAME)
    title.setObjectName("Title")
    title.setAlignment(Qt.AlignCenter)
    title.setLayoutDirection(Qt.LeftToRight)
    column.addWidget(title)

    subtitle = QLabel("إزالة البرنامج" if uninstalling
                      else "%s — الإصدار %s" % (TAGLINE, VERSION))
    subtitle.setObjectName("Hint")
    subtitle.setAlignment(Qt.AlignCenter)
    column.addWidget(subtitle)

    column.addSpacing(6)

    path_row = QHBoxLayout()
    path_label = QLabel("مجلد التثبيت")
    path_label.setObjectName("Hint")
    path_field = QLineEdit(installed_location() or default_target())
    path_field.setLayoutDirection(Qt.LeftToRight)
    browse = QPushButton("تصفّح…")
    browse.setFixedWidth(90)
    path_row.addWidget(path_label)
    path_row.addWidget(path_field, 1)
    path_row.addWidget(browse)
    column.addLayout(path_row)

    desktop_check = QCheckBox("اختصار على سطح المكتب")
    desktop_check.setChecked(True)
    menu_check = QCheckBox("اختصار في قائمة ابدأ")
    menu_check.setChecked(True)
    options = QHBoxLayout()
    options.addWidget(desktop_check)
    options.addWidget(menu_check)
    options.addStretch(1)
    column.addLayout(options)

    if uninstalling:
        path_field.setReadOnly(True)
        desktop_check.hide()
        menu_check.hide()
        path_label.setText("سيُحذف من")

    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.hide()
    column.addWidget(bar)

    status = QLabel("")
    status.setObjectName("Hint")
    status.setAlignment(Qt.AlignCenter)
    column.addWidget(status)

    column.addStretch(1)

    footer = QHBoxLayout()
    credit = QLabel("%s · %s" % (PUBLISHER, COPYRIGHT))
    credit.setObjectName("Hint")
    action = QPushButton("إزالة" if uninstalling else "تثبيت")
    action.setProperty("kind", "danger" if uninstalling else "primary")
    action.setMinimumWidth(140)
    footer.addWidget(credit)
    footer.addStretch(1)
    footer.addWidget(action)
    column.addLayout(footer)

    state = {"drag": None, "done": False}

    def press(event):
        if event.button() == Qt.LeftButton:
            state["drag"] = (event.globalPosition().toPoint()
                             - window.frameGeometry().topLeft())

    def move(event):
        if state["drag"] is not None and event.buttons() & Qt.LeftButton:
            window.move(event.globalPosition().toPoint() - state["drag"])

    def release(_event):
        state["drag"] = None

    window.mousePressEvent = press
    window.mouseMoveEvent = move
    window.mouseReleaseEvent = release

    def choose():
        folder = QFileDialog.getExistingDirectory(window, "اختر مجلد التثبيت")
        if folder:
            path_field.setText(os.path.join(folder, APP_NAME))

    browse.clicked.connect(choose)

    def finish(message):
        state["done"] = True
        status.setText(message)
        bar.setValue(100)
        action.setText("إغلاق")
        action.setProperty("kind", None)
        action.setStyleSheet("")
        action.setEnabled(True)

    def run():
        if state["done"]:
            window.close()
            return

        action.setEnabled(False)
        browse.setEnabled(False)
        bar.show()

        if uninstalling:
            status.setText("جاري الإزالة…")
            app.processEvents()
            target = do_uninstall()
            finish("أُزيل البرنامج من\n%s" % (target or "الجهاز"))
            return

        target = path_field.text().strip() or default_target()
        try:
            status.setText("جاري نسخ الملفات…")
            app.processEvents()

            def progress(done, total, name):
                bar.setValue(int(90 * done / max(1, total)))
                if done % 25 == 0 or done == total:
                    status.setText(os.path.basename(name))
                    app.processEvents()

            size = extract_payload(target, progress)

            status.setText("إنشاء الاختصارات…")
            app.processEvents()
            exe = os.path.join(target, EXE_NAME)
            uninstaller = os.path.join(target, "uninstall.exe")
            try:
                import shutil
                shutil.copy2(sys.executable, uninstaller)
            except Exception:
                uninstaller = None

            if desktop_check.isChecked():
                make_shortcut(os.path.join(desktop_dir(), APP_NAME + ".lnk"),
                              exe)
            if menu_check.isChecked():
                make_shortcut(os.path.join(start_menu_dir(), APP_NAME + ".lnk"),
                              exe)
                if uninstaller:
                    make_shortcut(
                        os.path.join(start_menu_dir(),
                                     "إزالة %s.lnk" % APP_NAME),
                        uninstaller, exe, "--uninstall")

            register(target, max(1, size // 1024))
            finish("تمّ التثبيت في\n%s" % target)
        except Exception as exc:
            bar.setValue(0)
            finish("فشل التثبيت: %s" % exc)

    action.clicked.connect(run)

    window.show()
    sys.exit(app.exec())


def main():
    if uninstall_mode() and "--silent" in sys.argv:
        do_uninstall()
        return
    run_gui()


if __name__ == "__main__":
    main()
