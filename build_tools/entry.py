"""
نقطة دخول ملف الـ exe.

تختلف عن main.py في أنها تستورد الحزمة باسم مثبّت وقت البناء بدل اشتقاقه من
مسار الملف، لأن PyInstaller يفكّ الموارد في مجلد مؤقّت لا يحمل اسم المشروع.
اسم الحزمة يكتبه ملف الوصفة app.spec في _pkg.py قبل البناء.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARENT = os.path.dirname(_ROOT)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

try:
    from _pkg import NAME as _PKG          # يُولَّد وقت البناء
except ImportError:
    _PKG = os.path.basename(_ROOT)         # التشغيل من المصدر مباشرة


def run():
    module = __import__(_PKG + ".main", fromlist=["main"])
    module.main()


if __name__ == "__main__":
    run()
