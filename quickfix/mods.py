import json
import os
import platform
import subprocess
import tempfile

import requests

from quickfix import INSTALLED_MODS_FILE
from quickfix.paths import get_appdata_dir
from quickfix.api import debug_print, get_latest_release_info, get_steam_game_name
from quickfix.security import extract_zip_safe
from quickfix.steam import find_steam_game_install_path


# ---------------------------------------------------------------------------
# installed.json helpers
# ---------------------------------------------------------------------------

def load_installed_mods():
    """Load installed.json and auto-migrate legacy format entries.

    Legacy format:  {"ModId": "v1.0.0"}
    New format:     {"ModId": {"version": "v1.0.0", "files": [], "game_appid": null}}
    """
    installed_path = os.path.join(get_appdata_dir(), INSTALLED_MODS_FILE)
    if not os.path.exists(installed_path):
        return {}

    with open(installed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    migrated = False
    for mod_id, value in data.items():
        if isinstance(value, str):
            # Legacy format - auto-migrate
            data[mod_id] = {"version": value, "files": [], "game_appid": None}
            migrated = True

    if migrated:
        save_installed_mods(data)
        print("[INFO] Migrated installed.json to new format.")

    return data


def save_installed_mods(mods):
    """Persist the installed mods dict to disk."""
    installed_path = os.path.join(get_appdata_dir(), INSTALLED_MODS_FILE)
    with open(installed_path, "w", encoding="utf-8") as f:
        json.dump(mods, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------

def download_mod_zip(download_url):
    """Download a mod zip from *download_url* and return the temp file path."""
    print(f"[INFO] Downloading mod from {download_url}...")
    response = requests.get(download_url, stream=True, timeout=30)
    response.raise_for_status()

    temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")
    os.close(temp_fd)

    with open(temp_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    debug_print(f"Downloaded mod zip to: {temp_path}")
    return temp_path


# ---------------------------------------------------------------------------
# Install / update / uninstall
# ---------------------------------------------------------------------------

def install_mod(mod_id, mods, force=False):
    mod = mods.get(mod_id)
    if not mod:
        print(f"[ERROR] Mod ID {mod_id} not found.")
        return

    repo = mod["repo"]
    games = mod.get("games", [])

    if not games:
        print(f"[WARN] No games defined for mod {mod_id}.")
        return

    version, download_url, _checksum_url = get_latest_release_info(repo)
    if not version or not download_url:
        print(f"[ERROR] Could not retrieve latest release for {mod_id}.")
        return

    installed_mods = load_installed_mods()

    for game in games:
        appid = game["steam_appid"]
        game_name = get_steam_game_name(appid)
        install_path = find_steam_game_install_path(appid)

        if not install_path:
            print(f"[WARN] Could not find install path for {game_name}")
            continue

        # Check if already up to date
        if mod_id in installed_mods:
            installed_version = installed_mods[mod_id].get("version", installed_mods[mod_id]) if isinstance(installed_mods[mod_id], dict) else installed_mods[mod_id]
            if installed_version == version and not force:
                print(f"[INFO] Mod {mod_id} is already up to date for {game_name}. Skipping.")
                continue

        print(f"[INFO] Installing {mod_id} for {game_name} ({version})...")
        zip_path = None
        try:
            zip_path = download_mod_zip(download_url)
            extracted_files = extract_zip_safe(zip_path, install_path)
            installed_mods[mod_id] = {
                "version": version,
                "files": extracted_files,
                "game_appid": appid,
            }
            save_installed_mods(installed_mods)
            print(f"[INFO] Installation complete for {game_name}!")
        finally:
            if zip_path and os.path.exists(zip_path):
                os.remove(zip_path)


def install_all_mods(mods):
    print("[INFO] Scanning all available mods for installed games...")
    for mod_id in mods.keys():
        install_mod(mod_id, mods, force=False)


def update_mod(mod_id, mods):
    """Update a specific mod."""
    installed_mods = load_installed_mods()
    if mod_id not in installed_mods:
        print(f"[ERROR] Mod ID {mod_id} is not installed.")
        return

    mod = mods.get(mod_id)
    if not mod:
        print(f"[ERROR] Mod ID {mod_id} not found in available mods.")
        return

    repo = mod["repo"]
    latest_version, _, _ = get_latest_release_info(repo)

    if not latest_version:
        print(f"[ERROR] Could not retrieve the latest version for mod {mod_id}.")
        return

    entry = installed_mods[mod_id]
    installed_version = entry.get("version") if isinstance(entry, dict) else entry
    if installed_version == latest_version:
        print(f"[INFO] Mod {mod_id} is already up to date (version {installed_version}). Skipping update.")
        return

    print(f"[INFO] Updating mod {mod_id} from version {installed_version} to {latest_version}...")
    install_mod(mod_id, mods, force=True)


def update_all_mods(mods):
    """Update all installed mods."""
    installed_mods = load_installed_mods()
    if not installed_mods:
        print("[INFO] No mods are currently installed.")
        return

    print("[INFO] Updating all installed mods...")
    for mod_id in list(installed_mods.keys()):
        update_mod(mod_id, mods)


def uninstall_mod(mod_id):
    """Uninstall a mod by removing its tracked files and installed.json entry."""
    installed_mods = load_installed_mods()
    if mod_id not in installed_mods:
        print(f"[ERROR] Mod ID {mod_id} is not installed.")
        return

    entry = installed_mods[mod_id]
    files = entry.get("files", []) if isinstance(entry, dict) else []
    game_appid = entry.get("game_appid") if isinstance(entry, dict) else None

    if files and game_appid:
        install_path = find_steam_game_install_path(game_appid)
        if install_path:
            removed = 0
            for rel_path in files:
                full_path = os.path.join(install_path, rel_path)
                if os.path.isfile(full_path):
                    os.remove(full_path)
                    removed += 1
                    debug_print(f"Removed: {full_path}")

            # Clean up empty directories left behind
            dirs_to_check = set()
            for rel_path in files:
                parent = os.path.dirname(os.path.join(install_path, rel_path))
                while parent != install_path and parent:
                    dirs_to_check.add(parent)
                    parent = os.path.dirname(parent)

            for d in sorted(dirs_to_check, key=len, reverse=True):
                try:
                    if os.path.isdir(d) and not os.listdir(d):
                        os.rmdir(d)
                        debug_print(f"Removed empty dir: {d}")
                except OSError:
                    pass

            print(f"[INFO] Removed {removed} file(s) for {mod_id}.")
        else:
            print(f"[WARN] Could not find game install path for appid {game_appid}. Removing tracking entry only.")
    elif not files:
        print(f"[WARN] Mod {mod_id} was installed before file tracking. Only removing from installed.json.")
    else:
        print(f"[WARN] No game appid recorded for {mod_id}. Removing tracking entry only.")

    del installed_mods[mod_id]
    save_installed_mods(installed_mods)
    print(f"[INFO] Uninstalled {mod_id}.")


# ---------------------------------------------------------------------------
# List / config helpers
# ---------------------------------------------------------------------------

def list_installed_mods():
    """List all installed mods and their versions."""
    installed_mods = load_installed_mods()
    if not installed_mods:
        print("[INFO] No mods are currently installed.")
        return

    print("[INFO] Installed mods:")
    for mod_id, entry in installed_mods.items():
        if isinstance(entry, dict):
            version = entry.get("version", "unknown")
            has_files = bool(entry.get("files"))
            status = "uninstallable" if has_files else "tracking only"
            print(f"- {mod_id}: {version} ({status})")
        else:
            print(f"- {mod_id}: {entry} (legacy format)")


def open_config_files(mod_id, mods):
    mod = mods.get(mod_id)
    if not mod:
        print(f"[ERROR] Mod ID {mod_id} not found.")
        return

    config_files = mod.get("config_files", [])
    games = mod.get("games", [])

    if not config_files:
        print(f"[WARN] No config files defined for {mod_id}.")
        return
    if not games:
        print(f"[WARN] No games defined for {mod_id}.")
        return

    for game in games:
        appid = game["steam_appid"]
        game_name = get_steam_game_name(appid)
        install_path = find_steam_game_install_path(appid)

        if not install_path:
            print(f"[WARN] Could not find install path for {game_name}.")
            continue

        print(f"[INFO] Searching for config files for {game_name}...")

        for config_name in config_files:
            found_path = None
            for root, _dirs, filenames in os.walk(install_path):
                if config_name in filenames:
                    found_path = os.path.join(root, config_name)
                    break

            if found_path:
                print(f"[INFO] Opening config file: {found_path}")
                if platform.system() == "Windows":
                    os.startfile(found_path)
                else:
                    subprocess.run(["open", found_path])
            else:
                print(f"[WARN] Could not find {config_name} inside {install_path} for {game_name}.")

    print(f"[INFO] Finished processing config files for {mod_id}.")
