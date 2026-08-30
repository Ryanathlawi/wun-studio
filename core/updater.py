"""
التحقّق من وجود إصدار أحدث على GitHub.

بلا Qt، وبلا استثناءات تصعد للأعلى: انقطاع الشبكة يرجع None بصمت، لأن فحص
التحديث لا يجوز أن يعطّل تشغيل البرنامج ولا أن يزعج من يشتغل بلا إنترنت.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from ..i18n import t

API = "https://api.github.com/repos/%s/releases/latest"
TIMEOUT = 6
NUMBERS = re.compile(r"\d+")


def parse(text):
    if not text:
        return ()
    return tuple(int(n) for n in NUMBERS.findall(str(text))[:4])


def _aligned(current, latest):
    a, b = parse(current), parse(latest)
    width = max(len(a), len(b), 3)
    return (a + (0,) * (width - len(a)), b + (0,) * (width - len(b)))


def is_newer(current, latest):
    if not parse(latest):
        return False
    a, b = _aligned(current, latest)
    return b > a


def kind(current, latest):
    a, b = _aligned(current, latest)
    if b[0] != a[0]:
        return "major"
    if b[1] != a[1]:
        return "minor"
    return "patch"


def kind_label(name):
    return {
        "major": t("تحديث كبير"),
        "minor": t("مزايا جديدة"),
        "patch": t("إصلاحات"),
    }.get(name, t("تحديث"))


def fetch(repo, timeout=TIMEOUT):
    request = urllib.request.Request(
        API % repo,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "WunStudio"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    tag = data.get("tag_name") or ""
    if not tag:
        return None
    return {
        "tag": tag,
        "version": tag.lstrip("vV"),
        "title": data.get("name") or tag,
        "notes": (data.get("body") or "").strip(),
        "url": data.get("html_url") or "",
        "date": (data.get("published_at") or "")[:10],
    }


def check(repo, current, timeout=TIMEOUT):
    """يرجع بيانات الإصدار الأحدث، أو None إن لم يوجد جديد أو تعذّر الوصول."""
    latest = fetch(repo, timeout)
    if not latest or not is_newer(current, latest["version"]):
        return None
    latest["kind"] = kind(current, latest["version"])
    latest["kind_label"] = kind_label(latest["kind"])
    return latest
