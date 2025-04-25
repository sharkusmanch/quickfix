import argparse
import os
import sys
import requests
import zipfile
import io
import json
import shutil
import time
from datetime import datetime
from colorama import Fore, Style, init

# Initialize Colorama
init(autoreset=True)

# Constants
QUICKFIX_VERSION = "0.1.0"
MOD_MARKER_FILENAME = ".quickfix"
CACHE_FILE = ".cache/mods.json"
CACHE_EXPIRY_SECONDS = 3600  # 1 hour
MODS_JSON_URL = "https://raw.githubusercontent.com/sharkusmanch/quickfix/master/mods.json"
DEFAULT_STEAM_PATH = "C:/Program Files (x86)/Steam"

# Utilities
def print_info(message):
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {message}")

def print_success(message):
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}")

def print_warning(message):
    print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}")

def print_error(message):
    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")

# Core Functions
def fetch_remote_mods_json():
    response = requests.get(MODS_JSON_URL)
    response.raise_for_status()
    return response.json()

def load_mods(custom_mods_path=None, force_refresh=False):
    if custom_mods_path:
        if not os.path.exists(custom_mods_path):
            print_error(f"Custom mods file '{custom_mods_path}' not found.")
            sys.exit(1)
        with open(custom_mods_path, "r") as f:
            return json.load(f)

    if force_refresh or not os.path.exists(CACHE_FILE) or (time.time() - os.path.getmtime(CACHE_FILE)) > CACHE_EXPIRY_SECONDS:
        print_info("Fetching latest mods.json from GitHub...")
        mods = fetch_remote_mods_json()
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(mods, f, indent=2)
    else:
        print_info("Using cached mods.json...")
        with open(CACHE_FILE, "r") as f:
            mods = json.load(f)

    return mods

def get_installed_games():
    steamapps_path = os.path.join(DEFAULT_STEAM_PATH, "steamapps", "common")
    if not os.path.exists(steamapps_path):
        print_error("Steam library not found at expected location.")
        sys.exit(1)
    return {game: os.path.join(steamapps_path, game) for game in os.listdir(steamapps_path)}

def find_game_path(game_name):
    installed = get_installed_games()
    for name, path in installed.items():
        if game_name.lower() in name.lower():
            return path
    return None

def write_mod_marker(install_path, mod_id, game_name, version):
    marker = {
        "mod_name": mod_id,
        "game_name": game_name,
        "version": version,
        "installed_at": datetime.utcnow().isoformat()
    }
    with open(os.path.join(install_path, MOD_MARKER_FILENAME), "w") as f:
        json.dump(marker, f, indent=2)

def get_installed_version(install_path):
    marker_path = os.path.join(install_path, MOD_MARKER_FILENAME)
    if not os.path.exists(marker_path):
        return None
    with open(marker_path, "r") as f:
        marker = json.load(f)
        return marker.get("version")

def fetch_release_info(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    token = os.getenv("GITHUB_TOKEN")
    headers = {'Authorization': f'token {token}'} if token else {}
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        return None, None
    if response.status_code != 200:
        print_error(f"Failed to fetch release info for {repo} (HTTP {response.status_code})")
        return None, None

    release_info = response.json()
    version = release_info.get("tag_name")
    assets = release_info.get("assets", [])
    if not assets:
        print_error(f"No assets found for {repo}")
        return None, None

    asset = assets[0]
    download_url = asset["browser_download_url"]
    return version.lstrip("v"), download_url

def download_and_extract(url, install_path):
    response = requests.get(url)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        zip_ref.extractall(install_path)

def install_mod(mod_id, mods, force=False):
    mod = mods.get(mod_id)
    if not mod:
        print_error(f"Mod {mod_id} not found.")
        return

    games = mod.get("games", [])
    if not games:
        print_warning(f"No associated games for {mod_id}. Skipping.")
        return

    # Find installed game
    for game in games:
        game_name = game["name"]
        install_path = find_game_path(game_name)
        if install_path:
            version, download_url = fetch_release_info(mod["repo"])
            if not version or not download_url:
                return

            installed_version = get_installed_version(install_path)
            if installed_version == version and not force:
                print_success(f"{mod_id} is already up-to-date ({version}).")
                return

            print_info(f"Installing {mod_id} for {game_name} (v{version})...")
            download_and_extract(download_url, install_path)
            write_mod_marker(install_path, mod_id, game_name, version)
            print_success(f"Installed {mod_id} at {install_path}")
            return

    print_warning(f"No matching installed game found for {mod_id}.")

def update_mod(mod_id, mods):
    install_mod(mod_id, mods, force=False)

def install_all_mods(mods):
    print_info("Scanning all available mods for installed games...")
    for mod_id in mods:
        install_mod(mod_id, mods, force=False)

def update_all_mods(mods):
    print_info("Checking for updates for all installed mods...")
    for mod_id in mods:
        install_mod(mod_id, mods, force=False)

def list_mods(mods):
    print_info("Available mods:")
    for mod_id, mod in mods.items():
        print(f"- {mod_id}")

def list_installed_mods(mods):
    installed = get_installed_games()
    found_any = False
    for mod_id, mod in mods.items():
        for game in mod.get("games", []):
            game_path = find_game_path(game["name"])
            if game_path and os.path.exists(os.path.join(game_path, MOD_MARKER_FILENAME)):
                version = get_installed_version(game_path)
                print(f"- {mod_id} (version {version}) installed for {game['name']}")
                found_any = True
    if not found_any:
        print_info("No installed mods found.")

# Main CLI
def main():
    parser = argparse.ArgumentParser(description="QuickFix - Lightweight Manager for Lyall's Game Fixes and Patches")
    parser.add_argument("--mods", help="Path to a custom mods.json file", default=None)
    parser.add_argument("--force-refresh", action="store_true", help="Force download fresh mods.json from GitHub")
    parser.add_argument("--version", action="store_true", help="Show QuickFix version and exit")

    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Install a mod")
    install_parser.add_argument("mod_id", nargs="?")
    install_parser.add_argument("--all", action="store_true", help="Install all available mods")

    update_parser = subparsers.add_parser("update", help="Update a mod")
    update_parser.add_argument("mod_id", nargs="?")
    update_parser.add_argument("--all", action="store_true", help="Update all installed mods")

    subparsers.add_parser("list", help="List available mods")
    subparsers.add_parser("installed", help="List installed mods")

    args = parser.parse_args()

    if args.version:
        print(f"QuickFix version {QUICKFIX_VERSION}")
        sys.exit(0)

    mods = load_mods(custom_mods_path=args.mods, force_refresh=args.force_refresh)

    if args.command == "install":
        if args.all:
            install_all_mods(mods)
        else:
            if not args.mod_id:
                print_error("Please specify a mod ID to install.")
                sys.exit(1)
            install_mod(args.mod_id, mods)
    elif args.command == "update":
        if args.all:
            update_all_mods(mods)
        else:
            if not args.mod_id:
                print_error("Please specify a mod ID to update.")
                sys.exit(1)
            update_mod(args.mod_id, mods)
    elif args.command == "list":
        list_mods(mods)
    elif args.command == "installed":
        list_installed_mods(mods)
    else:
        print_error("Unknown command.")
        sys.exit(1)

if __name__ == "__main__":
    main()
