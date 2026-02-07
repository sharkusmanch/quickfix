import json
import os
import time

from quickfix.paths import get_appdata_dir
from quickfix.api import fetch_latest_mods_json

CACHE_TTL_HOURS = 6
_CACHE_META_FILE = "cache_meta.json"
_MODS_CACHE_FILE = "mods.json"


def _cache_paths():
    appdata_dir = get_appdata_dir()
    return (
        os.path.join(appdata_dir, _MODS_CACHE_FILE),
        os.path.join(appdata_dir, _CACHE_META_FILE),
    )


def _is_cache_valid(meta_path):
    """Return True if the cache metadata exists and is less than CACHE_TTL_HOURS old."""
    if not os.path.exists(meta_path):
        return False
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        fetched_at = meta.get("fetched_at", 0)
        age_hours = (time.time() - fetched_at) / 3600
        return age_hours < CACHE_TTL_HOURS
    except Exception:
        return False


def _write_cache(mods_data, mods_path, meta_path):
    """Write mods data and cache metadata to disk."""
    with open(mods_path, "w", encoding="utf-8") as f:
        json.dump(mods_data, f, indent=2, ensure_ascii=False)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"fetched_at": time.time()}, f)


def get_mods(force_remote=False):
    """Return the mods dict, using a time-based cache (6h TTL).

    If *force_remote* is True the cache is bypassed and a fresh copy is fetched.
    """
    mods_path, meta_path = _cache_paths()

    if not force_remote and _is_cache_valid(meta_path) and os.path.exists(mods_path):
        try:
            with open(mods_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass  # fall through to remote fetch

    mods_data = fetch_latest_mods_json()
    _write_cache(mods_data, mods_path, meta_path)
    return mods_data
