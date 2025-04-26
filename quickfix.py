import argparse
import json
import os
import requests
import subprocess
import tempfile
import zipfile
import time
import platform
import re
import winreg
from datetime import datetime

__version__ = "1.0.3"

DEBUG_MODE = False
INSTALLED_MODS_FILE = "installed.json"

def debug_print(message):
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")

def github_get(url):
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")

    if token:
        debug_print(f"🔒 Authenticated GitHub request: {url}")
        headers["Authorization"] = f"Bearer {token}"
    else:
        debug_print(f"🌐 Public GitHub request: {url}")

    return requests.get(url, headers=headers, timeout=10)

def fetch_latest_mods_json():
    url = "https://raw.githubusercontent.com/sharkusmanch/quickfix/master/mods.json"
    print("[INFO] Fetching latest mods.json from GitHub...")
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()

def load_installed_mods():
    appdata_path = os.getenv("APPDATA")
    installed_mods_path = os.path.join(appdata_path, "QuickFix", INSTALLED_MODS_FILE)
    if os.path.exists(installed_mods_path):
        with open(installed_mods_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def save_installed_mods(mods):
    appdata_path = os.getenv("APPDATA")
    installed_mods_path = os.path.join(appdata_path, "QuickFix", INSTALLED_MODS_FILE)
    os.makedirs(os.path.dirname(installed_mods_path), exist_ok=True)
    with open(installed_mods_path, "w", encoding="utf-8") as f:
        json.dump(mods, f, indent=2, ensure_ascii=False)

def get_steam_root():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
        return steam_path
    except Exception as e:
        print(f"[WARN] Failed to read Steam path from registry: {e}")
        return None

def parse_libraryfolders(steam_root):
    libraries = []
    libraryfolders_path = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
    if not os.path.exists(libraryfolders_path):
        return libraries

    try:
        with open(libraryfolders_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_path = None
        for line in lines:
            line = line.strip()
            if '"path"' in line:
                match = re.search(r'"path"\s+"([^"]+)"', line)
                if match:
                    current_path = match.group(1).replace('\\\\', '\\')
                    libraries.append(os.path.join(current_path, "steamapps"))
    except Exception as e:
        print(f"[WARN] Failed to parse libraryfolders.vdf: {e}")

    libraries.append(os.path.join(steam_root, "steamapps"))
    return libraries

def get_install_dir_from_manifest(manifest_path):
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'"installdir"\s+"([^"]+)"', content)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"[WARN] Failed to parse manifest {manifest_path}: {e}")
    return None

def find_steam_game_install_path(appid):
    steam_root = get_steam_root()
    if not steam_root or not os.path.isdir(steam_root):
        print("[ERROR] Steam root directory not found.")
        return None

    library_paths = parse_libraryfolders(steam_root)
    debug_print(f"Steam libraries to scan: {library_paths}")

    for library_path in library_paths:
        appmanifest_path = os.path.join(library_path, f"appmanifest_{appid}.acf")
        if os.path.exists(appmanifest_path):
            install_dir_name = get_install_dir_from_manifest(appmanifest_path)
            if install_dir_name:
                full_path = os.path.join(library_path, "common", install_dir_name)
                debug_print(f"Checking for game install path: {full_path}")
                if os.path.exists(full_path):
                    return full_path
    return None

def get_steam_game_name(appid):
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=us&l=en"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data[str(appid)]["success"]:
            return data[str(appid)]["data"]["name"]
    except Exception:
        pass
    return f"Steam App {appid}"

def install_mod(mod_id, mods, force=False):
    mod = mods.get(mod_id)
    if not mod:
        print(f"[ERROR] Mod ID {mod_id} not found.")
        return

    repo = mod["repo"]
    config_files = mod.get("config_files", [])
    games = mod.get("games", [])

    if not games:
        print(f"[WARN] No games defined for mod {mod_id}.")
        return

    version, download_url = get_latest_release_info(repo)
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

        # Check if the mod is installed and if the version needs an update
        if mod_id in installed_mods:
            installed_version = installed_mods[mod_id]
            if installed_version == version and not force:
                print(f"[INFO] Mod {mod_id} is already up to date for {game_name}. Skipping.")
                continue

        print(f"[INFO] Installing {mod_id} for {game_name} ({version})...")
        try:
            zip_path = download_mod_zip(download_url)
            extract_zip(zip_path, install_path)
            installed_mods[mod_id] = version  # Update version in installed mods
            save_installed_mods(installed_mods)  # Save the updated installed mods info
            print(f"[INFO] Installation complete for {game_name}!")
        finally:
            if os.path.exists(zip_path):
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

    print(f"[INFO] Updating mod {mod_id}...")
    install_mod(mod_id, mods, force=True)

def update_all_mods(mods):
    """Update all installed mods."""
    installed_mods = load_installed_mods()
    if not installed_mods:
        print("[INFO] No mods are currently installed.")
        return

    print("[INFO] Updating all installed mods...")
    for mod_id in installed_mods.keys():
        update_mod(mod_id, mods)

def update_cache():
    print("[INFO] Fetching latest mods.json from GitHub and updating local cache...")
    mods_json = fetch_latest_mods_json()
    save_local_mods_json(mods_json)
    print("[INFO] Cache updated successfully.")

def save_local_mods_json(mods):
    # Get the AppData path and define the folder for QuickFix
    appdata_path = os.getenv("APPDATA")
    quickfix_path = os.path.join(appdata_path, "QuickFix")

    # Create the QuickFix directory if it doesn't exist
    if not os.path.exists(quickfix_path):
        os.makedirs(quickfix_path)

    LOCAL_MODS_JSON = os.path.join(quickfix_path, "mods.json")

    with open(LOCAL_MODS_JSON, "w", encoding="utf-8") as f:
        json.dump(mods, f, indent=2, ensure_ascii=False)

def download_mod_zip(download_url):
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

def extract_zip(zip_path, extract_to):
    print(f"[INFO] Extracting mod zip to {extract_to}...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)

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

    # Iterate over all games associated with the mod
    for game in games:
        appid = game["steam_appid"]
        game_name = get_steam_game_name(appid)
        install_path = find_steam_game_install_path(appid)

        if not install_path:
            print(f"[WARN] Could not find install path for {game_name}.")
            continue

        print(f"[INFO] Searching for config files for {game_name}...")

        # Search for each config file in the game's install path
        for config_name in config_files:
            found_path = None

            # Search recursively inside install_path
            for root, dirs, files in os.walk(install_path):
                if config_name in files:
                    found_path = os.path.join(root, config_name)
                    break

            if found_path:
                print(f"[INFO] Opening config file: {found_path}")
                if platform.system() == "Windows":
                    os.startfile(found_path)
                else:
                    subprocess.run(["open", found_path])  # macOS/Linux
            else:
                print(f"[WARN] Could not find {config_name} inside {install_path} for {game_name}.")

    print(f"[INFO] Finished processing config files for {mod_id}.")

def get_latest_release_info(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = github_get(url)

    if response.status_code == 200:
        release_data = response.json()
        version = release_data.get("tag_name", "unknown")
        download_url = release_data.get("assets", [{}])[0].get("browser_download_url")

        if not download_url:
            print(f"[ERROR] No download URL found for the latest release of {repo}.")
            return None, None

        return version, download_url
    else:
        print(f"[ERROR] Could not fetch release info for {repo}.")
        return None, None

def list_installed_mods():
    """List all installed mods and their versions."""
    installed_mods = load_installed_mods()
    if not installed_mods:
        print("[INFO] No mods are currently installed.")
        return

    print("[INFO] Installed mods:")
    for mod_id, version in installed_mods.items():
        print(f"- {mod_id}: {version}")

def main():
    global DEBUG_MODE

    parser = argparse.ArgumentParser(description="QuickFix - Manage Lyall's PC Game Fixes")
    parser.add_argument("command", choices=["install", "update", "update-cache", "open-config", "list-mods", "list-installed"], help="Command to run")
    parser.add_argument("mod_id", nargs="?", help="Mod ID to install, update, or open config (for 'install', 'update', or 'open-config' command)")
    parser.add_argument("--all", action="store_true", help="Install or update all mods")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--version", action="version", version=__version__, help="Show the version")

    args = parser.parse_args()

    DEBUG_MODE = args.debug

    # Get the AppData path and define the folder for QuickFix
    appdata_path = os.getenv("APPDATA")
    quickfix_path = os.path.join(appdata_path, "QuickFix")

    mods = fetch_latest_mods_json()

    if args.command == "install":
        if args.all:
            install_all_mods(mods)
        elif args.mod_id:
            install_mod(args.mod_id, mods)
        else:
            print("[ERROR] Please specify a mod ID or --all")
    elif args.command == "update":
        if args.all:
            update_all_mods(mods)
        elif args.mod_id:
            update_mod(args.mod_id, mods)
        else:
            print("[ERROR] Please specify a mod ID or --all")
    elif args.command == "update-cache":
        update_cache()  # Force update cache
    elif args.command == "open-config":
        if args.mod_id:
            open_config_files(args.mod_id, mods)
        else:
            print("[ERROR] Please specify a mod ID to open its config files.")
    elif args.command == "list-mods":
        print("[INFO] Listing all available mods:")
        for mod_id in mods.keys():
            print(f"- {mod_id}")
    elif args.command == "list-installed":
        list_installed_mods()

if __name__ == "__main__":
    main()
