import json
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests

from derive_mod_metadata import KNOWN_PROXY_DLLS

API_TOKEN = os.environ.get("CODEBERG_TOKEN")
CODEBERG_API = "https://codeberg.org/api/v1"

ALLOWED_LOADERS = {"ual", "bepinex", "melonloader"}
ALLOWED_LAYOUTS = {"flat", "pathed"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def codeberg_get(url, retries=3):
    headers = {}
    if API_TOKEN:
        headers["Authorization"] = f"token {API_TOKEN}"
    for attempt in range(retries):
        response = requests.get(url, headers=headers, timeout=10)
        # 4xx is a definitive answer (e.g. repo gone) — only retry transient errors.
        if response.status_code < 500:
            return response
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    return response


def _unsafe_subdir(subdir):
    return subdir.startswith("/") or any(p == ".." for p in subdir.split("/"))


def validate_entry(mod_id, mod):
    """Pure per-entry validation. Returns a list of error strings (empty = valid)."""
    errors = []
    if not mod.get("repo"):
        errors.append("missing repo")
    if not mod.get("config_files"):
        errors.append("missing config_files")

    for game in mod.get("games", []):
        appid = game.get("steam_appid")
        if not isinstance(appid, int):
            errors.append(f"invalid steam_appid: {appid!r}")
        subdir = game.get("install_subdir")
        if subdir is not None and _unsafe_subdir(subdir):
            errors.append(f"unsafe install_subdir: {subdir!r}")

    override = mod.get("wine_dll_override")
    if override is not None and override not in KNOWN_PROXY_DLLS:
        errors.append(f"unknown wine_dll_override: {override!r}")
    if mod.get("loader") is not None and mod["loader"] not in ALLOWED_LOADERS:
        errors.append(f"unknown loader: {mod['loader']!r}")
    if mod.get("zip_layout") is not None and mod["zip_layout"] not in ALLOWED_LAYOUTS:
        errors.append(f"unknown zip_layout: {mod['zip_layout']!r}")

    if mod.get("derived_release"):
        if not SHA256_RE.match(str(mod.get("sha256", ""))):
            errors.append("bad or missing sha256 for derived entry")
        url = urlparse(str(mod.get("download_url", "")))
        if url.scheme != "https" or url.hostname != "codeberg.org":
            errors.append(f"bad download_url: {mod.get('download_url')!r}")
        if not isinstance(mod.get("size"), int) or mod["size"] <= 0:
            errors.append("bad or missing size for derived entry")
    return errors


def collect_cross_mod_warnings(mods):
    warnings = []
    seen_appids = {}
    for mod_id, mod in mods.items():
        if not mod.get("games"):
            warnings.append(f"{mod_id}: empty games[] — mod matches no installed game")
        for game in mod.get("games", []):
            appid = game.get("steam_appid")
            if appid in seen_appids and seen_appids[appid] != mod_id:
                warnings.append(f"appid {appid} claimed by both {seen_appids[appid]} and {mod_id}")
            seen_appids.setdefault(appid, mod_id)
    return warnings


def validate_mods():
    if not os.path.exists("mods.json"):
        print("❌ mods.json not found.")
        sys.exit(1)
    try:
        with open("mods.json", "r", encoding="utf-8") as f:
            mods = json.load(f)
    except Exception as e:
        print(f"❌ Failed to parse mods.json: {e}")
        sys.exit(1)

    failed = False
    for mod_id, mod in mods.items():
        print(f"🔎 Checking mod: {mod_id}")
        errors = validate_entry(mod_id, mod)
        for error in errors:
            print(f"❌ {mod_id}: {error}")
            failed = True
        if mod.get("repo"):
            response = codeberg_get(f"{CODEBERG_API}/repos/{mod['repo']}")
            if response.status_code != 200:
                # Legacy GitHub-only fixes (pre-Codeberg-migration) 404 here; they
                # simply never get derived metadata, so warn rather than fail.
                print(f"⚠️ {mod_id}: Codeberg repo '{mod['repo']}' not found.")

    for warning in collect_cross_mod_warnings(mods):
        print(f"⚠️ {warning}")

    if failed:
        sys.exit(1)
    print("✅ All checks passed for mods.json!")


if __name__ == "__main__":
    validate_mods()
