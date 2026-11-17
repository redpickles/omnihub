"""Backup support: one-file export and import of OmniHub's data and icons.

The Settings tab's **Export data…** / **Import data…** buttons move everything
through a single **.zip** archive. Zip won on simplicity: `zipfile` is stdlib (7z
has no stdlib support, and `.gz` alone can't hold several files so it would mean
tar.gz), and Windows Explorer opens `.zip` natively.

Archive layout:

    manifest.json      what's inside, where each file came from, and when it was made
    folders.json       data files, stored at the archive root by basename
    apps.json
    settings.json      copied for reference only — never restored, it names one machine's paths
    icons/NNN-name.ico every icon the App Launcher uses

Icons live next to the app files rather than in the data folder, so a backup of
the JSONs alone would lose them. That's why they're collected explicitly and
their original location recorded, so an import can put them back.

This module never imports `app.py`: the caller hands in the data folder, the app
list, an icon resolver and the app name. That keeps the archive format testable
in isolation and avoids a circular import.
"""

import json
import os
import zipfile
from datetime import datetime

MANIFEST_NAME = "manifest.json"
FORMAT_VERSION = 1  # bump when the archive layout changes
DATA_FILENAMES = ("folders.json", "apps.json")  # restorable files, by name in the data folder
SETTINGS_FILENAME = "settings.json"  # archived for reference, never restored
ICON_DIR = "icons"
COMPRESSED = ".zip"


class BackupError(Exception):
    """A backup file can't be read, or isn't something we can restore."""


def default_export_name(prefix, *, when=None):
    """Suggested archive filename: `<prefix>-2026-11-17.zip`.

    The date in the name keeps a folder of backups sortable without opening
    anything. `prefix` comes from the caller (`app.py` builds it from `APP_NAME`)
    so this module doesn't hard-code the app's name.
    """
    return f"{prefix}-{(when or datetime.now()).strftime('%Y-%m-%d')}{COMPRESSED}"


def collect_icons(apps, icon_resolver):
    """Return `[(arcname, source, app_path)]` for the icons an app list uses.

    `icon_resolver(app_path)` gives the `.ico` OmniHub shows for that app, or
    `None`. Several apps in one folder can share a single `favicon.ico`, so each
    distinct file is stored once; the leading index keeps archive names unique
    even when two folders hold identically named icons.
    """
    entries = []
    seen = set()
    for index, app in enumerate(apps, start=1):
        path = app.get("path")
        if not path:
            continue
        source = icon_resolver(path)
        if not source or not os.path.isfile(source):
            continue
        key = os.path.normcase(source)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            (f"{ICON_DIR}/{index:03d}-{os.path.basename(source)}", source, path)
        )
    return entries


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _write_bytes_atomic(path, blob):
    """Write `blob` to `path` atomically (temp file + rename).

    Same idiom as `_atomic_write` in `app.py`, kept local so a half-written
    restore can never replace a good file — and so this module stays standalone.
    """
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(blob)
    os.replace(tmp, path)


def export_zip(dest, *, data_folder, settings_file, apps, icon_resolver, app_name, version):
    """Write a backup archive to `dest`, overwriting it if it exists.

    Keyword-only after `dest` so the call site stays readable. Returns
    ``{"data": [...], "icons": [...], "notes": [...]}``, where `notes` describes
    anything asked for but not included, so a partial export can be reported
    instead of quietly shrinking the backup.
    """
    dest = os.path.abspath(dest)
    manifest = {
        "format": FORMAT_VERSION,
        "app": app_name,
        "app_version": version,
        "exported": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_folder": data_folder,
        "data": [],
        "icons": [],
        "reference": [],
    }
    data, icons, notes = [], [], []

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in DATA_FILENAMES:
            source = os.path.join(data_folder, name)
            if not os.path.isfile(source):
                notes.append(f"no such data file to export: {name}")
                continue
            archive.write(source, name)
            manifest["data"].append(name)
            data.append(name)

        # settings.json lives next to the app, not in the data folder, and it
        # records one machine's paths — so it travels as reference only.
        if os.path.isfile(settings_file):
            archive.write(settings_file, SETTINGS_FILENAME)
            manifest["reference"].append(SETTINGS_FILENAME)

        for arcname, source, app_path in collect_icons(apps, icon_resolver):
            try:
                archive.write(source, arcname)
            except OSError as exc:  # deleted or locked between listing and reading
                notes.append(f"couldn't read the icon for {app_path}: {exc}")
                continue
            manifest["icons"].append({"arcname": arcname, "source": source, "app": app_path})
            icons.append(arcname)

        archive.writestr(
            MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        )

    return {"data": data, "icons": icons, "notes": notes}


def read_manifest(path, *, app_name):
    """Return an archive's manifest, verified well enough to restore from.

    Raises `BackupError` if `path` isn't a readable backup made by this app.
    """
    try:
        with zipfile.ZipFile(path, "r") as archive:
            raw = archive.read(MANIFEST_NAME)
    except FileNotFoundError:
        raise BackupError(f"File not found:\n{path}") from None
    except (zipfile.BadZipFile, KeyError, OSError):
        raise BackupError(f"Not a readable zip archive:\n{path}") from None

    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise BackupError(f"Backup manifest is unreadable:\n{path}") from None

    if not isinstance(manifest, dict):
        raise BackupError(f"Backup manifest is unreadable:\n{path}")
    if manifest.get("app") != app_name:
        raise BackupError(f"This file isn't an {app_name} backup:\n{path}")
    if not isinstance(manifest.get("data", []), list):
        raise BackupError(f"Backup manifest is unreadable:\n{path}")
    try:
        archive_format = int(manifest.get("format", 1))
    except (TypeError, ValueError):
        raise BackupError(f"Backup manifest is unreadable:\n{path}") from None
    if archive_format > FORMAT_VERSION:
        raise BackupError(
            f"This backup was made by a newer version of {app_name}.\n"
            f"Update {app_name} before importing it."
        )
    if not manifest["data"]:
        raise BackupError(f"No data files inside this backup:\n{path}")
    return manifest


def import_zip(path, data_folder, *, app_name):
    """Restore a backup into `data_folder`. See `read_manifest` for validation.

    Data files are overwritten in place. Icons go back next to the app file they
    belong to, and only where that folder still exists — a gone app folder is
    reported, never recreated. Icons already matching byte-for-byte are left
    alone. Returns
    ``{"data": [...], "icons": [...], "identical": n, "notes": [...]}``.
    """
    manifest = read_manifest(path, app_name=app_name)
    if not os.path.isdir(data_folder):
        raise BackupError(f"The data folder doesn't exist:\n{data_folder}")

    report = {"data": [], "icons": [], "identical": 0, "notes": []}
    with zipfile.ZipFile(path, "r") as archive:
        for name in manifest["data"]:
            if not isinstance(name, str) or os.path.basename(name) != name:
                # No path tricks: data files always sit directly in the data folder.
                report["notes"].append(f"skipped unexpected entry: {name!r}")
                continue
            try:
                blob = archive.read(name)
            except KeyError:
                report["notes"].append(f"listed in the manifest but absent from the file: {name}")
                continue
            _write_bytes_atomic(os.path.join(data_folder, name), blob)
            report["data"].append(name)

        icon_entries = manifest.get("icons", [])
        if not isinstance(icon_entries, list):
            report["notes"].append("the manifest's icon section is unreadable")
            icon_entries = []
        for entry in icon_entries:
            if not isinstance(entry, dict):
                report["notes"].append("manifest entry without an icon location")
                continue
            arcname, source = entry.get("arcname"), entry.get("source")
            if not arcname or not source:
                report["notes"].append("manifest entry without an icon location")
                continue
            if not os.path.isdir(os.path.dirname(source)):
                report["notes"].append(f"folder gone, icon skipped: {source}")
                continue
            try:
                blob = archive.read(arcname)
            except KeyError:
                report["notes"].append(f"listed in the manifest but absent from the file: {arcname}")
                continue
            if os.path.isfile(source) and _read_bytes(source) == blob:
                report["identical"] += 1
                continue
            try:
                _write_bytes_atomic(source, blob)
            except OSError as exc:
                report["notes"].append(f"couldn't restore {source}: {exc}")
                continue
            report["icons"].append(source)

    return report
