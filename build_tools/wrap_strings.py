"""
لفّ نصوص الواجهة العربية بدالة الترجمة t().

    python build_tools/wrap_strings.py gui/main_window.py ...
    python build_tools/wrap_strings.py --list        # سرد النصوص فقط

يعمل على مستوى الرموز لا على شجرة الكود، فلا تُفقد التعليقات ولا التنسيق.
يتخطّى التوثيق، ويجمع النصوص المتلاصقة في لفّة واحدة حتى لا ينكسر التركيب.
"""

from __future__ import annotations

import ast
import glob
import io
import os
import re
import sys
import tokenize

ARABIC = re.compile(r"[؀-ۿ]")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def docstring_positions(source):
    positions = set()
    tree = ast.parse(source)
    targets = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if not isinstance(node, targets):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            positions.add((first.value.lineno, first.value.col_offset))
    return positions


def _is_code(value):
    """ورقة أنماط أو قالب كود لا نص واجهة."""
    if len(value) > 400:
        return True
    markers = ("background:", "border-radius", "QWidget", "font-family",
               "<svg", "stop:", "px;")
    return any(marker in value for marker in markers)


def groups(source):
    """مجموعات النصوص المتلاصقة التي تحوي عربية، مع مواضعها."""
    docs = docstring_positions(source)
    reader = io.StringIO(source).readline
    tokens = list(tokenize.generate_tokens(reader))

    result = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type != tokenize.STRING:
            index += 1
            continue

        run = [token]
        cursor = index + 1
        while cursor < len(tokens):
            following = tokens[cursor]
            if following.type == tokenize.STRING:
                run.append(following)
                cursor += 1
            elif following.type in (tokenize.NL, tokenize.COMMENT):
                cursor += 1
            else:
                break

        if any(t.start in docs for t in run):
            index = cursor
            continue

        text = "".join(t.string for t in run)
        try:
            value = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            index = cursor
            continue

        if isinstance(value, str) and ARABIC.search(value)                 and not _is_code(value):
            result.append((run[0].start, run[-1].end, value))
        index = cursor
    return result


IDENT = re.compile(r"[A-Za-z0-9_]")


def already_wrapped(lines, start):
    row, col = start
    prefix = lines[row - 1][:col].rstrip()
    if not prefix.endswith("t("):
        return False
    before = prefix[:-2]
    # setText( و setPlaceholderText( تنتهي بـ t( كذلك، فنتحقّق مما قبلها
    return not (before and IDENT.match(before[-1]))


def wrap(path, dry_run=False):
    source = io.open(path, encoding="utf-8").read()
    lines = source.splitlines(keepends=True)
    spans = groups(source)

    edits = []
    values = []
    for start, end, value in spans:
        if already_wrapped(lines, start):
            continue
        edits.append((start, end))
        values.append(value)

    if dry_run or not edits:
        return values, 0

    # الاستبدال من الآخر إلى الأول حتى لا تنزاح المواضع
    for start, end in reversed(edits):
        (srow, scol), (erow, ecol) = start, end
        if srow == erow:
            line = lines[srow - 1]
            lines[srow - 1] = (line[:scol] + "t(" + line[scol:ecol] + ")"
                               + line[ecol:])
        else:
            first = lines[srow - 1]
            lines[srow - 1] = first[:scol] + "t(" + first[scol:]
            last = lines[erow - 1]
            lines[erow - 1] = last[:ecol] + ")" + last[ecol:]

    text = "".join(lines)
    if "from ..i18n import t" not in text and "from .i18n import t" not in text:
        depth = 2 if os.path.basename(os.path.dirname(path)) in ("gui", "core") \
            else 1
        statement = "from %si18n import t\n" % ("." * depth)
        marker = "from __future__ import annotations\n"
        if marker in text:
            text = text.replace(marker, marker + "\n" + statement, 1)
        else:
            text = statement + text

    io.open(path, "w", encoding="utf-8", newline="").write(text)
    return values, len(edits)


def main(argv):
    dry = "--list" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        paths = sorted(glob.glob(os.path.join(ROOT, "gui", "*.py"))) + \
                sorted(glob.glob(os.path.join(ROOT, "core", "*.py")))

    everything = []
    total = 0
    for path in paths:
        if os.path.basename(path) == "i18n.py":
            continue
        values, count = wrap(path, dry)
        everything.extend(values)
        total += count
        if count:
            print("%-30s %d" % (os.path.relpath(path, ROOT), count))

    unique = sorted(set(everything))
    print("\nمواضع مُعدَّلة: %d | نصوص فريدة: %d" % (total, len(unique)))

    out = os.path.join(ROOT, "build", "strings.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as handle:
        for value in unique:
            handle.write(repr(value) + "\n")
    print("القائمة في:", out)


if __name__ == "__main__":
    main(sys.argv[1:])
