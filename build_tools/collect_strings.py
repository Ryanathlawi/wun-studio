"""
جمع كل النصوص المارّة بدالة الترجمة t() في ملف واحد.

    python build_tools/collect_strings.py

يقرأ شجرة الكود لا الرموز، فيلتقط النصوص المتلاصقة مجموعةً واحدة كما تصل
إلى t() تمامًا. المخرجات هي مفاتيح EN_MAP الفعلية.
"""

from __future__ import annotations

import ast
import glob
import io
import os
import re
import sys

ARABIC = re.compile(r"[؀-ۿ]")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def calls(path):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "t"):
            continue
        if not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            found.append(arg.value)
    return found


def loose(path):
    """نصوص عربية لم تُلفّ بعد."""
    source = io.open(path, encoding="utf-8").read()
    tree = ast.parse(source)
    wrapped = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "t" and node.args):
            arg = node.args[0]
            if isinstance(arg, ast.Constant):
                wrapped.add((arg.lineno, arg.col_offset))

    docs = set()
    targets = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, targets) and body:
            first = body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docs.add((first.value.lineno, first.value.col_offset))

    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        where = (node.lineno, node.col_offset)
        if where in wrapped or where in docs:
            continue
        if ARABIC.search(node.value) and len(node.value) < 400:
            out.append((node.lineno, node.value))
    return out


def main():
    paths = sorted(glob.glob(os.path.join(ROOT, "gui", "*.py"))) + \
            sorted(glob.glob(os.path.join(ROOT, "core", "*.py")))

    everything = []
    stragglers = []
    for path in paths:
        if os.path.basename(path) == "i18n.py":
            continue
        everything.extend(calls(path))
        for line, value in loose(path):
            stragglers.append((os.path.relpath(path, ROOT), line, value))

    unique = sorted(set(everything))
    out = os.path.join(ROOT, "build", "strings.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as handle:
        for value in unique:
            handle.write(repr(value) + "\n")

    print("استدعاءات t(): %d | نصوص فريدة: %d" % (len(everything), len(unique)))
    print("لم تُلفّ بعد: %d" % len(stragglers))
    for rel, line, value in stragglers[:40]:
        print("   %s:%d  %s" % (rel, line, value[:70]))

    sys.path.insert(0, ROOT)
    en = __import__("i18n").EN_MAP
    missing = [value for value in unique if value not in en]
    stale = [key for key in en if key not in set(unique)]
    print("\nبلا ترجمة إنجليزية: %d" % len(missing))
    for value in missing:
        print("   %r" % value)
    print("ترجمات لم تعد مستعملة: %d" % len(stale))
    for key in stale:
        print("   %r" % key)


if __name__ == "__main__":
    main()
