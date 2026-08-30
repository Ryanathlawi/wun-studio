from __future__ import annotations

import os
import re
import shutil

MANIFEST_NAMES = ("fxmanifest.lua", "__resource.lua")
META_EXTENSIONS = (".meta", ".xml", ".ymt")
STREAM_DIR = "stream"

SCRIPT_KEYS = ("client_script", "server_script", "shared_script",
               "client_scripts", "server_scripts", "shared_scripts",
               "ui_page", "dependency", "provide", "export")

_SINGLE = re.compile(r"^\s*(fx_version|game|lua54|author|description|version)"
                     r"\s+'([^']*)'", re.M)
_FILES_BLOCK = re.compile(r"files\s*\{(.*?)\}", re.S)
_QUOTED = re.compile(r"'([^']+)'")
_DATA_FILE = re.compile(r"^\s*data_file\s+'([^']+)'\s+'([^']+)'", re.M)


class MergeError(Exception):
    pass


class Resource:

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.name = os.path.basename(self.path)
        self.stream = os.path.join(self.path, STREAM_DIR)
        self.stream_files = []
        self.root_files = []
        self.manifest_name = None
        self.manifest = {}
        self.stream_bytes = 0
        self.error = None
        self._load()

    def _load(self):
        if not os.path.isdir(self.path):
            self.error = "المجلد غير موجود"
            return
        if not os.path.isdir(self.stream):
            self.error = "لا يوجد مجلد stream داخل المورد"
            return

        for entry in os.listdir(self.stream):
            full = os.path.join(self.stream, entry)
            if os.path.isfile(full):
                self.stream_files.append(entry)
                self.stream_bytes += os.path.getsize(full)

        for entry in os.listdir(self.path):
            full = os.path.join(self.path, entry)
            if not os.path.isfile(full):
                continue
            if entry.lower() in MANIFEST_NAMES:
                self.manifest_name = entry
                self.manifest = parse_manifest(
                    open(full, encoding="utf-8", errors="replace").read())
            elif entry.lower().endswith(META_EXTENSIONS):
                self.root_files.append(entry)

    @property
    def has_scripts(self):
        return bool(self.manifest.get("scripts"))


def parse_manifest(text):
    data = {"single": {}, "files": [], "data_files": [], "scripts": []}
    for key, value in _SINGLE.findall(text):
        data["single"][key] = value

    for block in _FILES_BLOCK.findall(text):
        data["files"].extend(_QUOTED.findall(block))

    for kind, path in _DATA_FILE.findall(text):
        data["data_files"].append((kind, path))

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        for key in SCRIPT_KEYS:
            if re.match(r"^%s\b" % key, stripped):
                data["scripts"].append(stripped)
                break
    return data


def scan(paths):
    return [Resource(path) for path in paths]


class MergePlan:

    def __init__(self, resources):
        self.resources = [r for r in resources if not r.error]
        self.broken = [r for r in resources if r.error]
        self.stream_map = {}
        self.stream_clashes = []
        self.root_map = {}
        self.root_clashes = []
        self.total_bytes = 0
        self._build()

    def _build(self):
        seen = {}
        for resource in self.resources:
            for name in resource.stream_files:
                key = name.lower()
                if key in seen:
                    self.stream_clashes.append((name, seen[key].name,
                                                resource.name))
                    continue
                seen[key] = resource
                self.stream_map[name] = os.path.join(resource.stream, name)
                self.total_bytes += os.path.getsize(self.stream_map[name])

        seen_root = {}
        for resource in self.resources:
            for name in resource.root_files:
                key = name.lower()
                if key in seen_root:
                    self.root_clashes.append((name, seen_root[key].name,
                                              resource.name))
                    continue
                seen_root[key] = resource
                self.root_map[name] = os.path.join(resource.path, name)

    @property
    def file_count(self):
        return len(self.stream_map)

    @property
    def script_resources(self):
        return [r for r in self.resources if r.has_scripts]

    def manifest(self, resource_name="merged_clothing", author="Athlawi"):
        singles = {}
        for resource in self.resources:
            for key, value in resource.manifest.get("single", {}).items():
                singles.setdefault(key, value)

        files = []
        data_files = []
        for resource in self.resources:
            for name in resource.manifest.get("files", []):
                if name not in files:
                    files.append(name)
            for entry in resource.manifest.get("data_files", []):
                if entry not in data_files:
                    data_files.append(entry)

        for name in sorted(self.root_map):
            if name not in files:
                files.append(name)

        lines = [
            "fx_version '%s'" % singles.get("fx_version", "cerulean"),
            "game '%s'" % singles.get("game", "gta5"),
        ]
        if singles.get("lua54"):
            lines.append("lua54 '%s'" % singles["lua54"])
        lines.append("")
        lines.append("author '%s'" % author)
        lines.append("description 'دُمج بواسطة Wun Studio من %d مورد: %s'"
                     % (len(self.resources),
                        "، ".join(r.name for r in self.resources)))
        lines.append("")

        if files:
            lines.append("files {")
            for name in files:
                lines.append("    '%s'," % name)
            lines.append("}")
            lines.append("")

        for kind, path in data_files:
            lines.append("data_file '%s' '%s'" % (kind, path))
        if data_files:
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"


def plan(resources) -> MergePlan:
    return MergePlan(resources)


def apply(merge_plan: MergePlan, out_dir, resource_name="merged_clothing",
          progress=None, move=False, author="Athlawi"):
    target = os.path.join(out_dir, resource_name)
    stream = os.path.join(target, STREAM_DIR)
    os.makedirs(stream, exist_ok=True)

    copied, failed = 0, []
    items = sorted(merge_plan.stream_map.items())
    for index, (name, source) in enumerate(items):
        if progress is not None and not progress(index, len(items), name):
            break
        try:
            destination = os.path.join(stream, name)
            if move:
                shutil.move(source, destination)
            else:
                shutil.copy2(source, destination)
            copied += 1
        except OSError as exc:
            failed.append((name, str(exc)))

    for name, source in sorted(merge_plan.root_map.items()):
        try:
            shutil.copy2(source, os.path.join(target, name))
        except OSError as exc:
            failed.append((name, str(exc)))

    manifest_path = os.path.join(target, "fxmanifest.lua")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(merge_plan.manifest(resource_name, author))

    return target, copied, failed


def summary(merge_plan: MergePlan):
    return {
        "resources": len(merge_plan.resources),
        "broken": len(merge_plan.broken),
        "files": merge_plan.file_count,
        "bytes": merge_plan.total_bytes,
        "stream_clashes": len(merge_plan.stream_clashes),
        "root_clashes": len(merge_plan.root_clashes),
        "scripts": len(merge_plan.script_resources),
    }
