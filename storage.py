"""Storage management: where media files live and where new ones go.

StreamCast keeps media on one or more "storages" — a directory root that
holds uploads/ and encoded/ subfolders. The main storage (id 1) is the
env-driven config.STORAGE_DIR and always exists; admins can add more roots
(e.g. an external SSD) in the admin panel. Every video row records which
storage each of its copies lives on (videos.storage_id / encoded_storage_id /
prev_encoded_storage_id); NULL chains fall back to the main storage, which
keeps pre-multi-storage rows working unchanged.

This module is the ONLY place that turns those ids into filesystem paths —
consumers never build media paths from config constants directly.
"""
import shutil
from pathlib import Path
import platform
import os

import config
import db

MIN_FREE = config.MIN_FREE_GB * 1024 ** 3   # stop writing below this watermark


# --- Path resolution ---------------------------------------------------------
def root(storage_row):
    """Directory root of a storage row."""
    if storage_row["path"] is None:
        return config.STORAGE_DIR
    return Path(storage_row["path"]).expanduser().resolve()


def upload_dir(storage_row):
    return root(storage_row) / "uploads"


def encoded_dir(storage_row):
    return root(storage_row) / "encoded"


def ensure_dirs(storage_row):
    ensure_dirs_at(root(storage_row))


def ensure_dirs_at(p):
    """Create the uploads/encoded tree under a root path (used by validation
    before the row exists)."""
    (p / "uploads").mkdir(parents=True, exist_ok=True)
    (p / "encoded").mkdir(parents=True, exist_ok=True)


def ensure_all():
    """Create the tree for the main storage and every registered one.
    Storages whose disk is unplugged are skipped, not fatal."""
    for row in db.list_storages():
        try:
            ensure_dirs(row)
        except OSError:
            pass


def storage_for(video, *columns):
    """Resolve a video row's storage via a fallback chain of columns
    (NULL = fall through), ending at the main storage."""
    for col in columns:
        sid = video[col] if col in video.keys() else None
        if sid:
            row = db.get_storage(sid)
            if row:
                return row
    return db.get_storage(1)


def video_upload_path(video):
    """Original uploaded file of a video row."""
    return upload_dir(storage_for(video, "storage_id")) / video["stored_name"]


def video_encoded_path(video, name=None):
    """Encoded copy of a video row, or an explicit copy name. The
    prev-quality copy is resolved through its own storage column."""
    row = storage_for(video, "encoded_storage_id", "storage_id")
    if name is None:
        name = video["encoded_name"]
    elif "prev_encoded_name" in video.keys() and name == video["prev_encoded_name"]:
        row = storage_for(video, "prev_encoded_storage_id",
                          "encoded_storage_id", "storage_id")
    return encoded_dir(row) / name


def video_thumb_path(video):
    """Thumbnail sits next to the encoded file: xxx.mp4 -> xxx.mp4.jpg."""
    return video_encoded_path(video).with_name(video["encoded_name"] + ".jpg")


def encoded_dir_for(video):
    """Which encoded/ directory a new copy of this video belongs in."""
    return encoded_dir(storage_for(video, "encoded_storage_id", "storage_id"))


# --- Capacity ----------------------------------------------------------------
def disk_status(storage_row):
    """free/total of a storage's disk, or ok=False when it can't be read
    (unplugged SSD, permissions)."""
    try:
        usage = shutil.disk_usage(root(storage_row))
    except Exception as e:
        import logging
        logging.error(f"Storage {storage_row['name']} error: {e}")
        return {"ok": False, "free_gb": 0.0, "total_gb": 0.0, "used_pct": 0.0}
    # Log disk usage for debugging second disk
    import logging
    logging.info(f"Disk {storage_row['name']} [{root(storage_row)}]: total={usage.total}, used={usage.used}, free={usage.free}")
    
    return {
        "ok": True,
        "free_gb": usage.free / 1024 ** 3,
        "total_gb": usage.total / 1024 ** 3,
        "used_pct": round(100 * usage.used / usage.total, 1) if usage.total else 0.0,
    }


def free_bytes(storage_row):
    """Free space on the storage's disk, or None when unreadable."""
    try:
        return shutil.disk_usage(root(storage_row)).free
    except OSError:
        return None


def available_bytes(storage_row):
    """Free space above the safety watermark, or None when offline."""
    free = free_bytes(storage_row)
    return None if free is None else free - MIN_FREE


def _default_id():
    for row in db.list_storages():
        if row["is_default"]:
            return row["id"]
    return 1


def default_storage():
    return db.get_storage(_default_id())


def _candidate_order(prefer_id):
    """Storages in preference order: the preferred one first, the rest by
    most free space. Offline storages are dropped."""
    scored = []
    for row in db.list_storages():
        avail = available_bytes(row)
        if avail is not None:
            scored.append((row, avail))
    preferred = [(r, a) for r, a in scored if r["id"] == prefer_id]
    rest = sorted((ra for ra in scored if ra[0]["id"] != prefer_id),
                  key=lambda ra: -ra[1])
    ordered = preferred + rest
    return [r for r, _ in ordered], {r["id"]: a for r, a in ordered}


def upload_targets(needed=0):
    """Storages that can take a new upload of `needed` bytes, best first
    (default storage when it fits, then others by free space)."""
    ordered, avail = _candidate_order(_default_id())
    return [r for r in ordered if avail[r["id"]] >= needed]


def encode_targets(prefer_id, needed=0):
    """Storages that can take an encoded copy, preferring the one the
    source (or previous copy) lives on, then others by free space."""
    ordered, avail = _candidate_order(prefer_id)
    return [r for r in ordered if avail[r["id"]] >= needed]


# --- Add validation ----------------------------------------------------------
class StorageError(Exception):
    """User-facing problem with a storage path (admin form)."""


def validate_new_storage(name, path_str):
    """Check an admin-supplied path; returns the normalized absolute path.
    Raises StorageError with a user-facing message."""
    name = (name or "").strip()
    path_str = (path_str or "").strip()
    if not name:
        raise StorageError("Name is required")
    if not path_str:
        raise StorageError("Path is required")
    p = Path(path_str).expanduser().resolve()

    for row in db.list_storages():
        other = root(row)
        if p == other or p in other.parents or other in p.parents:
            raise StorageError(f"Path overlaps storage «{row['name']}» ({other})")
    try:
        ensure_dirs_at(p)
        probe = p / ".streamcast_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        raise StorageError(f"Path is not usable: {e}")
    return str(p)


def scan_available_disks():
    """Scan system for available mount points and disks to suggest as storages.
    Returns a list of {name, path, free_gb, total_gb}."""
    found = []
    system = platform.system()

    if system == "Windows":
        import string
        for letter in string.ascii_uppercase:
            path = Path(f"{letter}:\\")
            if path.exists():
                try:
                    usage = shutil.disk_usage(path)
                    found.append({
                        "name": f"Disk {letter}:",
                        "path": str(path),
                        "free_gb": usage.free / 1024**3,
                        "total_gb": usage.total / 1024**3,
                    })
                except OSError:
                    continue
    else:
        for base in ("/mnt", "/media"):
            base_path = Path(base)
            if base_path.exists():
                for entry in base_path.iterdir():
                    if entry.is_dir():
                        try:
                            usage = shutil.disk_usage(entry)
                            found.append({
                                "name": entry.name,
                                "path": str(entry),
                                "free_gb": usage.free / 1024**3,
                                "total_gb": usage.total / 1024**3,
                            })
                        except OSError:
                            continue
    return found
