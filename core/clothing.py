from __future__ import annotations

import os
import re
import shutil

COMPONENTS = (
    "p_head", "p_eyes", "p_ears", "p_mouth", "p_lhand", "p_rhand",
    "p_lwrist", "p_rwrist", "p_hip", "p_lfoot", "p_rfoot",
    "head", "berd", "hair", "uppr", "lowr", "hand", "feet", "teef",
    "accs", "task", "decl", "jbib",
)

_COMP = "|".join(sorted(COMPONENTS, key=len, reverse=True))

YDD_RE = re.compile(
    r"^(?P<model>.+?)\^(?P<comp>%s)_(?P<num>\d{3})_(?P<suffix>[a-z])\.ydd$" % _COMP,
    re.IGNORECASE)
YTD_RE = re.compile(
    r"^(?P<model>.+?)\^(?P<comp>%s)_diff_(?P<num>\d{3})_(?P<letter>[a-z])"
    r"_(?P<suffix>\w+)\.ytd$" % _COMP,
    re.IGNORECASE)

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


class Entry:

    def __init__(self, kind, path, model, component, drawable, suffix,
                 letter=None):
        self.kind = kind
        self.path = path
        self.name = os.path.basename(path)
        self.model = model
        self.component = component
        self.drawable = drawable
        self.suffix = suffix
        self.letter = letter

    @property
    def key(self):
        return (self.model, self.component, self.drawable)

    def __repr__(self):
        return "<%s %s>" % (self.kind, self.name)


class Issue:

    def __init__(self, kind, severity, title, detail, fix=None, entries=None):
        self.kind = kind
        self.severity = severity
        self.title = title
        self.detail = detail
        self.fix = fix
        self.entries = entries or []

    @property
    def fixable(self):
        return self.fix is not None

    def __repr__(self):
        return "<%s %s>" % (self.severity, self.title)


class Fix:

    def __init__(self, kind, description, actions):
        self.kind = kind
        self.description = description
        self.actions = actions


class Index:

    def __init__(self, folder):
        self.folder = folder
        self.drawables = {}
        self.unmatched = []
        self.total_files = 0

    def slot(self, key):
        return self.drawables.setdefault(key, {"ydd": None, "ytd": {}})

    @property
    def models(self):
        return sorted({key[0] for key in self.drawables})

    def stats(self):
        ydd = sum(1 for s in self.drawables.values() if s["ydd"])
        ytd = sum(len(s["ytd"]) for s in self.drawables.values())
        return {
            "files": self.total_files,
            "drawables": len(self.drawables),
            "models": len(self.models),
            "ydd": ydd,
            "ytd": ytd,
            "unmatched": len(self.unmatched),
        }


def scan(folder, recursive=True) -> Index:
    index = Index(folder)
    walker = os.walk(folder) if recursive else [
        (folder, [], os.listdir(folder))]

    for root, _dirs, names in walker:
        for name in names:
            lower = name.lower()
            if not lower.endswith((".ydd", ".ytd")):
                continue
            index.total_files += 1
            path = os.path.join(root, name)

            match = YDD_RE.match(name)
            if match:
                data = match.groupdict()
                entry = Entry("ydd", path, data["model"].lower(),
                              data["comp"].lower(), int(data["num"]),
                              data["suffix"].lower())
                index.slot(entry.key)["ydd"] = entry
                continue

            match = YTD_RE.match(name)
            if match:
                data = match.groupdict()
                entry = Entry("ytd", path, data["model"].lower(),
                              data["comp"].lower(), int(data["num"]),
                              data["suffix"].lower(), data["letter"].lower())
                index.slot(entry.key)["ytd"][entry.letter] = entry
                continue

            index.unmatched.append(path)

    return index


def _sibling_texture(index, key):
    model, component, drawable = key
    candidates = []
    for other, slot in index.drawables.items():
        if other[0] != model or other[1] != component or other == key:
            continue
        if "a" in slot["ytd"]:
            candidates.append((abs(other[2] - drawable), slot["ytd"]["a"]))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _renamed(entry, drawable):
    parts = entry.name.split("^", 1)
    prefix, rest = parts[0], parts[1]
    rest = re.sub(r"_(\d{3})_", "_%03d_" % drawable, rest, count=1)
    return os.path.join(os.path.dirname(entry.path), "%s^%s" % (prefix, rest))


def diagnose(index: Index):
    issues = []

    for key in sorted(index.drawables):
        model, component, drawable = key
        slot = index.drawables[key]
        label = "%s^%s_%03d" % (model, component, drawable)

        if slot["ydd"] and not slot["ytd"]:
            source = _sibling_texture(index, key)
            fix = None
            if source is not None:
                target = os.path.join(
                    os.path.dirname(slot["ydd"].path),
                    "%s^%s_diff_%03d_a_%s.ytd"
                    % (model, component, drawable, source.suffix))
                fix = Fix("copy_texture",
                          "نسخ %s" % source.name,
                          [("copy", source.path, target)])
            issues.append(Issue(
                "missing_texture", "error",
                "%s بلا تكستشر" % label,
                "القطعة موجودة بلا أي ملف تكستشر، فتظهر في اللعبة بلا خامة.",
                fix, [slot["ydd"]]))

        if slot["ytd"] and not slot["ydd"]:
            entries = list(slot["ytd"].values())
            quarantine = os.path.join(index.folder, "_unused")
            fix = Fix("quarantine",
                      "نقل %d ملف إلى مجلد _unused" % len(entries),
                      [("move", e.path,
                        os.path.join(quarantine, e.name)) for e in entries])
            issues.append(Issue(
                "orphan_texture", "warning",
                "%s تكستشر بلا قطعة" % label,
                "توجد %d تكستشرات بلا ملف ydd يقابلها، وهي وزن ميت في المورد."
                % len(entries), fix, entries))

        if slot["ytd"]:
            present = sorted(ord(letter) - 97 for letter in slot["ytd"])
            missing = sorted(set(range(max(present) + 1)) - set(present))
            if missing:
                actions = []
                for slot_index in missing:
                    letter = chr(97 + slot_index)
                    earlier = [i for i in present if i < slot_index]
                    source_letter = chr(97 + (earlier[-1] if earlier
                                              else present[0]))
                    source = slot["ytd"][source_letter]
                    target = os.path.join(
                        os.path.dirname(source.path),
                        source.name.replace("_%s_%s." % (source_letter,
                                                         source.suffix),
                                            "_%s_%s." % (letter,
                                                         source.suffix)))
                    actions.append(("copy", source.path, target))
                issues.append(Issue(
                    "variant_gap", "warning",
                    "%s ينقصه تنويع %s" % (label, "، ".join(
                        chr(97 + i) for i in missing)),
                    "فجوة في حروف التنويعات تجعل اللعبة تقرأ تنويعًا غير موجود.",
                    Fix("copy_variant", "نسخ أقرب تنويع سابق", actions),
                    list(slot["ytd"].values())))

    groups = {}
    for model, component, drawable in index.drawables:
        groups.setdefault((model, component), set()).add(drawable)

    for (model, component), numbers in sorted(groups.items()):
        missing = sorted(set(range(max(numbers) + 1)) - numbers)
        if not missing:
            continue
        ordered = sorted(numbers)
        actions = []
        for new_index, old in enumerate(ordered):
            if new_index == old:
                continue
            slot = index.drawables[(model, component, old)]
            for entry in ([slot["ydd"]] if slot["ydd"] else []) + \
                    list(slot["ytd"].values()):
                actions.append(("rename", entry.path,
                                _renamed(entry, new_index)))
        issues.append(Issue(
            "drawable_gap", "error",
            "%s^%s ينقصه الرقم %s" % (model, component, "، ".join(
                "%03d" % n for n in missing[:6])),
            "ترقيم القطع يجب أن يكون متصلًا من صفر، وإلا انزاحت الفهارس في "
            "اللعبة فتختار قطعة وتظهر غيرها.",
            Fix("renumber", "إعادة ترقيم %d ملف" % len(actions), actions)
            if actions else None))

    if index.unmatched:
        issues.append(Issue(
            "bad_name", "info",
            "%d ملف خارج نمط التسمية" % len(index.unmatched),
            "ملفات لا تطابق نمط model^component_NNN. قد تكون ملفات أساس "
            "للموديل نفسه وليست ملابس."))

    issues.sort(key=lambda issue: (SEVERITY_ORDER[issue.severity], issue.title))
    return issues


def plan(issues, kinds=None):
    actions = []
    for issue in issues:
        if not issue.fixable:
            continue
        if kinds is not None and issue.fix.kind not in kinds:
            continue
        actions.extend(issue.fix.actions)
    return actions


def apply(actions, dry_run=True):
    done, failed = [], []
    # يُنفَّذ التغيير في مرحلتين: كل الوجهات تُكتب باسم مؤقت أولًا، فلا
    # تتصادم إعادة الترقيم مع ملف ما زال يحمل الاسم الهدف
    staged = []
    for kind, source, target in actions:
        if dry_run:
            done.append((kind, source, target))
            continue
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if kind == "copy":
                shutil.copy2(source, target)
                done.append((kind, source, target))
            else:
                temp = target + ".wunstage"
                shutil.move(source, temp)
                staged.append((kind, source, temp, target))
        except OSError as exc:
            failed.append((source, str(exc)))

    for kind, source, temp, target in staged:
        try:
            if os.path.exists(target):
                os.remove(target)
            shutil.move(temp, target)
            done.append((kind, source, target))
        except OSError as exc:
            failed.append((source, str(exc)))

    return done, failed


def summary(issues):
    counts = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        counts[issue.severity] += 1
    counts["fixable"] = sum(1 for issue in issues if issue.fixable)
    return counts
