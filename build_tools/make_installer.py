"""
بناء مثبّت Wun Studio كاملًا في خطوة واحدة.

    .venv\\Scripts\\python.exe build_tools/make_installer.py

يبني نسخة المجلد، يحزمها في payload.zip، ثم يبني ملف المثبّت الواحد.
النتيجة في dist_setup/Wun Studio Setup.exe
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "dist_dir", "Wun Studio")
PAYLOAD = os.path.join(ROOT, "build", "payload.zip")
PYTHON = sys.executable


def run(args, env=None):
    merged = dict(os.environ)
    if env:
        merged.update(env)
    result = subprocess.run(args, cwd=ROOT, env=merged)
    if result.returncode != 0:
        raise SystemExit("فشل: %s" % " ".join(args))


def build_app():
    print("[١/٣] بناء نسخة المجلد…")
    run([PYTHON, "-m", "PyInstaller", "build_tools/app.spec", "--noconfirm",
         "--distpath", "dist_dir", "--workpath", "build_dir"],
        {"WUN_ONEDIR": "1"})


def pack_payload():
    print("[٢/٣] حزم البرنامج في payload.zip…")
    if not os.path.isdir(APP_DIR):
        raise SystemExit("لم يُعثر على %s" % APP_DIR)
    os.makedirs(os.path.dirname(PAYLOAD), exist_ok=True)
    if os.path.exists(PAYLOAD):
        os.remove(PAYLOAD)

    started = time.time()
    count = 0
    with zipfile.ZipFile(PAYLOAD, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=6) as archive:
        for folder, _dirs, files in os.walk(APP_DIR):
            for name in files:
                full = os.path.join(folder, name)
                archive.write(full, os.path.relpath(full, APP_DIR))
                count += 1
    size = os.path.getsize(PAYLOAD)
    raw = sum(os.path.getsize(os.path.join(f, n))
              for f, _d, files in os.walk(APP_DIR) for n in files)
    print("      %d ملف · %.0f م.ب -> %.0f م.ب · %.0f ثانية"
          % (count, raw / 1e6, size / 1e6, time.time() - started))


def build_installer():
    print("[٣/٣] بناء ملف المثبّت…")
    run([PYTHON, "-m", "PyInstaller", "build_tools/installer.spec",
         "--noconfirm", "--distpath", "dist_setup",
         "--workpath", "build_setup"])
    out = os.path.join(ROOT, "dist_setup", "Wun Studio Setup.exe")
    if os.path.exists(out):
        print("\nجاهز: %s  (%.0f م.ب)" % (out, os.path.getsize(out) / 1e6))


def main():
    steps = sys.argv[1:] or ["app", "payload", "installer"]
    if "app" in steps:
        build_app()
    if "payload" in steps:
        pack_payload()
    if "installer" in steps:
        build_installer()


if __name__ == "__main__":
    main()
