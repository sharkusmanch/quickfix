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

__version__ = "1.0.0"

DEBUG_MODE = False

def debug_print(message):
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")

def github_get(url):
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")

    if token:
        debug_print(f"🔒 Authenticated GitHub request: {url}")  # Move to debug
        headers["Authorization"] = f"Bearer {token}"
    else:
        debug_print(f"🌐 Public GitHub request: {url}")  # Move to debug

    return requests.get(url, headers=headers, timeout=10)

def fetch_latest_mods_json():
    url = "https://raw.githubusercontent.com/sharkusmanch/quickfix/master/mods.json"
    print("[INFO] Fetching latest mods.json from GitHub...")
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()

def load_local_mods_json():
    # Get the AppData path and define the folder for QuickFix
    appdata_path = os.getenv("APPDATA")
    quickfix_path = os.path.join(appdata_path, "QuickFix")

    # Create the QuickFix directory if it doesn't exist
    if not os.path.exists(quickfix_path):
        os.makedirs(quickfix_path)

    LOCAL_MODS_JSON = os.path.join(quickfix_path, "mods.json")

    if os.path.exists(LOCAL_MODS_JSON):
        with open(LOCAL_MODS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

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

    for game in games:
        appid = game["steam_appid"]
        game_name = get_steam_game_name(appid)
        install_path = find_steam_game_install_path(appid)

        if not install_path:
            print(f"[WARN] Could not find install path for {game_name}")
            continue

        if not force and is_mod_already_installed(mod_id, install_path):
            print(f"[INFO] {mod_id} already installed for {game_name}. Skipping.")
            continue

        print(f"[INFO] Installing {mod_id} for {game_name} ({version})...")
        try:
            zip_path = download_mod_zip(download_url)
            extract_zip(zip_path, install_path)
            write_mod_marker(mod_id, version, install_path)
            print(f"[INFO] Installation complete for {game_name}!")
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

def install_all_mods(mods):
    print("[INFO] Scanning all available mods for installed games...")
    for mod_id in mods.keys():
        install_mod(mod_id, mods, force=False)

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

    # Find the game install path
    for game in games:
        appid = game["steam_appid"]
        install_path = find_steam_game_install_path(appid)
        if install_path:
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
                    print(f"[WARN] Could not find {config_name} inside {install_path}.")
            return

    print(f"[WARN] Could not find installed game for {mod_id}.")


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

def is_mod_already_installed(mod_id, install_path):
    marker_file = os.path.join(install_path, ".quickfix")
    if os.path.exists(marker_file):
        with open(marker_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Check if the mod_id exists in the marker file and matches the version
            if data.get("mod_name") == mod_id:
                print(f"[INFO] Mod {mod_id} already installed.")
                return True
    return False

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

def write_mod_marker(mod_id, version, install_path):
    marker_file = os.path.join(install_path, ".quickfix")
    mod_data = {
        "mod_name": mod_id,
        "version": version,
        "installed_at": datetime.now().isoformat()
    }

    with open(marker_file, "w", encoding="utf-8") as f:
        json.dump(mod_data, f, indent=2, ensure_ascii=False)

    print(f"[INFO] Wrote installation marker for {mod_id} at {marker_file}")

def list_available_mods(mods):
    """Lists all available mods."""
    if not mods:
        print("[INFO] No mods available.")
        return

    print(f"\n[INFO] Available mods: {len(mods)}")
    for mod_id, mod in mods.items():
        print(f"\nMod ID: {mod_id}")
        print(f"  Repo: {mod['repo']}")
        print(f"  Config files: {', '.join(mod.get('config_files', []))}")
        for game in mod.get("games", []):
            print(f"  Steam AppID: {game.get('steam_appid')}")

def main():
    global DEBUG_MODE

    parser = argparse.ArgumentParser(description="QuickFix - Manage Lyall's PC Game Fixes")
    parser.add_argument("command", choices=["install", "update", "open-config", "list-mods"], help="Command to run")
    parser.add_argument("mod_id", nargs="?", help="Mod ID to install or open config (for 'install' or 'open-config' command)")
    parser.add_argument("--all", action="store_true", help="Install or update all mods")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    DEBUG_MODE = args.debug

    # Fetch and load latest mods.json from GitHub or local AppData
    mods = fetch_latest_mods_json()

    if args.command == "install":
        if args.all:
            install_all_mods(mods)
        elif args.mod_id:
            install_mod(args.mod_id, mods)
        else:
            print("[ERROR] Please specify a mod ID or --all")
    elif args.command == "update":
        save_local_mods_json(mods)
        print(f"[INFO] Updated mods.json in AppData directory.")
    elif args.command == "open-config":
        if args.mod_id:
            open_config_files(args.mod_id, mods)
        else:
            print("[ERROR] Please specify a mod ID to open its config files.")
    elif args.command == "list-mods":
        list_available_mods(mods)

if __name__ == "__main__":
    main()
