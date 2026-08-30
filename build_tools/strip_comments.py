"""
Strip comments and docstrings from Python sources.

    python build_tools/strip_comments.py core/rsc7.py core/ytd_handler.py

Writes each file back in place. Verifies that the stripped source still parses
and that its abstract syntax tree matches the original once docstrings are
discarded, so a mangled file can never be written.
"""

from __future__ import annotations

import ast
import io
import sys
import tokenize


def _docstring_spans(tree: ast.AST) -> set[tuple[int, int]]:
    spans = set()
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
            spans.add((first.lineno, first.end_lineno))
    return spans


def _comment_spans(source: str) -> dict[int, int]:
    """line number -> column where a comment starts."""
    spans = {}
    reader = io.StringIO(source).readline
    for tok in tokenize.generate_tokens(reader):
        if tok.type == tokenize.COMMENT:
            spans[tok.start[0]] = tok.start[1]
    return spans


def _needs_pass(tree: ast.AST, spans: set[tuple[int, int]]) -> set[int]:
    """Bodies that consist only of a docstring need a replacement statement."""
    lines = set()
    targets = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if isinstance(node, targets) and len(node.body) == 1:
            first = node.body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                lines.add(first.lineno)
    return lines


def _normalise(source: str) -> str:
    """AST dump with docstrings removed, used to prove nothing else changed."""
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
            rest = body[1:]
            # a module may legally end up empty; a def or class may not
            node.body = rest or ([] if isinstance(node, ast.Module)
                                 else [ast.Pass()])
    return ast.dump(ast.fix_missing_locations(tree))


def strip(source: str) -> str:
    tree = ast.parse(source)
    doc_spans = _docstring_spans(tree)
    comments = _comment_spans(source)
    pass_lines = _needs_pass(tree, doc_spans)

    drop = set()
    replace = {}
    for start, end in doc_spans:
        for line in range(start, end + 1):
            drop.add(line)
        if start in pass_lines:
            indent = len(source.splitlines()[start - 1]) - len(
                source.splitlines()[start - 1].lstrip())
            replace[start] = " " * indent + "pass"

    out = []
    for number, text in enumerate(source.splitlines(), start=1):
        if number in replace:
            out.append(replace[number])
            continue
        if number in drop:
            continue
        if number in comments:
            column = comments[number]
            head = text[:column].rstrip()
            if not head:
                continue                    # سطر تعليق كامل
            out.append(head)
            continue
        out.append(text.rstrip())

    # اطوِ الفراغات المتتالية الناتجة عن الحذف إلى سطر واحد كحد أقصى داخل
    # الدوال، وسطرين بين التعريفات على المستوى الأعلى
    collapsed = []
    blanks = 0
    for line in out:
        if not line.strip():
            blanks += 1
            continue
        limit = 2 if (line and not line[0].isspace()) else 1
        if collapsed:
            collapsed += [""] * min(blanks, limit)
        blanks = 0
        collapsed.append(line)

    result = "\n".join(collapsed).rstrip() + "\n"

    if _normalise(result) != _normalise(source):
        raise SystemExit("رُفض: شجرة الكود تغيّرت بعد التجريد")
    return result


def main(paths):
    for path in paths:
        with io.open(path, encoding="utf-8") as fh:
            source = fh.read()
        stripped = strip(source)
        with io.open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(stripped)
        before = source.count("\n") + 1
        after = stripped.count("\n") + 1
        print("%-28s %5d -> %5d سطرًا  (-%d)"
              % (path, before, after, before - after))


if __name__ == "__main__":
    main(sys.argv[1:])
