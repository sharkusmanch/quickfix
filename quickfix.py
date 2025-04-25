import os
import requests
import zipfile
import shutil
import json
import re
import configparser
import sys

from io import BytesIO
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

MOD_MARKER_FILENAME = ".quickfix"
DEFAULT_STEAM_PATH = "C:/Program Files (x86)/Steam"

# -------- Color print helpers --------

def print_success(message):
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")

def print_warning(message):
    print(f"{Fore.YELLOW}{message}{Style.RESET_ALL}")

def print_error(message):
    print(f"{Fore.RED}{message}{Style.RESET_ALL}")

def print_info(message):
    print(f"{Fore.CYAN}{message}{Style.RESET_ALL}")

# -------- Core functions --------



def load_mods(custom_mods_path=None):
    if custom_mods_path:
        if not os.path.exists(custom_mods_path):
            print_error(f"Custom mods file '{custom_mods_path}' not found.")
            sys.exit(1)
        with open(custom_mods_path, "r") as f:
            return json.load(f)
    else:
        # Load embedded mods.json relative to exe
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base_path, "mods.json"), "r") as f:
            return json.load(f)


def find_steam_libraries(steam_root):
    library_vdf = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
    libraries = [os.path.join(steam_root, "steamapps")]

    if not os.path.exists(library_vdf):
        raise FileNotFoundError(f"libraryfolders.vdf not found at {library_vdf}")

    with open(library_vdf, "r") as f:
        content = f.read()

    matches = re.findall(r'"\d+"\s*{\s*"path"\s*"([^"]+)"', content, re.MULTILINE)
    for match in matches:
        libraries.append(os.path.join(match.replace('\\\\', '\\'), "steamapps"))

    return libraries

def find_game_install_path(appid, steam_root=DEFAULT_STEAM_PATH):
    libraries = find_steam_libraries(steam_root)

    for library in libraries:
        manifest_path = os.path.join(library, f"appmanifest_{appid}.acf")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()
            install_dir_match = re.search(r'"installdir"\s+"([^"]+)"', content)
            if install_dir_match:
                install_dir = install_dir_match.group(1)
                return os.path.join(library, "common", install_dir)
    return None

def get_installable_games(mod):
    installable_games = []
    if "games" not in mod:
        return installable_games

    for game in mod["games"]:
        try:
            path = find_game_install_path(game["steam_appid"])
            if path:
                installable_games.append((game, path))
        except Exception:
            continue
    return installable_games

def download_zip(url):
    print_info(f"Downloading {url}...")
    response = requests.get(url)
    response.raise_for_status()
    return BytesIO(response.content)

# -------- New function for merging INI files --------

def merge_ini_configs(existing_config_path, new_config_path):
    old_config = configparser.ConfigParser()
    old_config.read(existing_config_path, encoding='utf-8')

    new_config = configparser.ConfigParser()
    new_config.read(new_config_path, encoding='utf-8')

    merged = configparser.ConfigParser()

    # Copy everything from new config first
    for section in new_config.sections():
        merged.add_section(section)
        for key, value in new_config.items(section):
            merged.set(section, key, value)

    # Now override with user's settings
    for section in old_config.sections():
        if not merged.has_section(section):
            merged.add_section(section)
        for key, value in old_config.items(section):
            merged.set(section, key, value)

    # Save merged config back to existing path
    with open(existing_config_path, "w", encoding='utf-8') as f:
        merged.write(f)

# -------- Updated extraction function --------

def extract_zip(zip_data, install_path, config_files):
    print_info(f"Installing to {install_path}...")
    with zipfile.ZipFile(zip_data) as z:
        for member in z.namelist():
            target_path = os.path.join(install_path, member)

            # Handle config files specially
            if any(member.endswith(config) for config in config_files):
                if os.path.exists(target_path):
                    # Extract new config temporarily
                    temp_new_config_path = target_path + ".new"
                    with open(temp_new_config_path, "wb") as f:
                        f.write(z.read(member))

                    print_info(f"Merging config {member}...")
                    merge_ini_configs(target_path, temp_new_config_path)

                    os.remove(temp_new_config_path)
                else:
                    z.extract(member, install_path)
            else:
                z.extract(member, install_path)
    print_success("Extraction complete.")

def write_mod_marker(install_path, mod_name, version, game_name):
    marker_path = os.path.join(install_path, MOD_MARKER_FILENAME)
    data = {
        "mod_name": mod_name,
        "game_name": game_name,
        "version": version,
        "installed_at": __import__('datetime').datetime.now().isoformat()
    }
    with open(marker_path, "w") as f:
        json.dump(data, f, indent=2)
    print_success(f"Wrote version marker at {marker_path}")

def get_installed_version(install_path):
    marker_path = os.path.join(install_path, MOD_MARKER_FILENAME)
    if not os.path.exists(marker_path):
        return None
    with open(marker_path, "r") as f:
        data = json.load(f)
    return data.get("version")

# -------- GitHub API functions --------

def get_latest_release_asset(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"

    token = os.getenv("GITHUB_TOKEN")
    headers = {'Authorization': f'token {token}'} if token else {}

    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        print_warning(f"No releases found for {repo}. Skipping.")
        return None, None
    if response.status_code != 200:
        print_error(f"Failed to fetch release info for {repo} (HTTP {response.status_code})")
        return None, None

    release_info = response.json()
    raw_version = release_info.get("tag_name")

    assets = release_info.get("assets", [])
    if not assets:
        print_error(f"No assets found for {repo}")
        return None, None

    asset = assets[0]
    download_url = asset["browser_download_url"]

    return raw_version, download_url


# -------- Install / Update Logic --------

def install_mod(mod_id, mods, force=False, version_override=None):
    if mod_id not in mods:
        print_error(f"Mod {mod_id} not found.")
        return

    mod = mods[mod_id]
    installable_games = get_installable_games(mod)

    if not installable_games:
        print_warning(f"No supported games installed for {mod_id}. Skipping.")
        return

    raw_version, download_url = get_latest_release_asset(mod["repo"])
    if not raw_version or not download_url:
        print_error(f"Could not retrieve latest release for {mod_id}")
        return

    latest_version = raw_version.lstrip('v')
    version_to_install = version_override or latest_version

    for game, install_path in installable_games:
        marker_path = os.path.join(install_path, MOD_MARKER_FILENAME)
        installed_version = None

        if os.path.exists(marker_path):
            with open(marker_path, "r") as f:
                data = json.load(f)
                installed_version = data.get("version")

        if installed_version == version_to_install and not force:
            print_success(f"{mod_id} ({game['name']}): Already up-to-date (v{installed_version}). Skipping.")
            continue

        print_info(f"Installing {mod_id} for {game['name']} (v{version_to_install})...")
        zip_data = download_zip(download_url)
        extract_zip(zip_data, install_path, mod.get("config_files", []))
        write_mod_marker(install_path, mod_id, version_to_install, game["name"])

def install_all_mods(mods):
    print_info("Scanning all available mods for installed games...")
    for mod_id in mods:
        install_mod(mod_id, mods, force=False)

def update_all_mods(mods):
    print_info("Checking all installed mods for updates...")
    for mod_id, mod in mods.items():
        installable_games = get_installable_games(mod)

        if not installable_games:
            continue

        raw_version, download_url = get_latest_release_asset(mod["repo"])
        if not raw_version or not download_url:
            print_error(f"- Failed to check {mod_id}, skipping.")
            continue

        latest_version = raw_version.lstrip('v')

        for game, install_path in installable_games:
            marker_path = os.path.join(install_path, MOD_MARKER_FILENAME)
            installed_version = None

            if os.path.exists(marker_path):
                with open(marker_path, "r") as f:
                    data = json.load(f)
                    installed_version = data.get("version")

            if not installed_version:
                print_warning(f"- {mod_id} ({game['name']}): Not installed, skipping.")
                continue

            if installed_version != latest_version:
                print_warning(f"- {mod_id} ({game['name']}): Needs update {installed_version} → {latest_version}")
                install_mod(mod_id, mods, force=True, version_override=latest_version)
            else:
                print_success(f"- {mod_id} ({game['name']}): Up-to-date (v{installed_version})")

def list_mods(mods):
    print_info("Available mods:")
    for mod_id in mods:
        print(f"- {mod_id}")

def list_installed(mods):
    print_info("Installed mods:")
    for mod_id, mod in mods.items():
        installable_games = get_installable_games(mod)

        for game, install_path in installable_games:
            version = get_installed_version(install_path)
            if version:
                print(f"- {mod_id} ({game['name']}) (v{version})")
            else:
                print_warning(f"- {mod_id} ({game['name']}) (not installed)")

# -------- CLI --------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="QuickFix - Lightweight Manager for Lyall's Game Fixes and Patches")
    parser.add_argument("--mods", help="Path to a custom mods.json file", default=None)

    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("mod_id", nargs="?", help="Install a specific mod")
    install_parser.add_argument("--all", action="store_true", help="Install all available mods for installed games")

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("mod_id", nargs="?", help="Update a specific mod")
    update_parser.add_argument("--all", action="store_true", help="Update all installed mods")

    subparsers.add_parser("list")
    subparsers.add_parser("installed")

    args = parser.parse_args()
    mods = load_mods(custom_mods_path=args.mods)

    if args.command == "install":
        if args.all:
            install_all_mods(mods)
        elif args.mod_id:
            install_mod(args.mod_id, mods, force=False)
        else:
            print_error("Specify a mod_id to install or use --all.")
    elif args.command == "update":
        if args.all:
            update_all_mods(mods)
        elif args.mod_id:
            install_mod(args.mod_id, mods, force=False)
        else:
            print_error("Specify a mod_id to update or use --all.")
    elif args.command == "list":
        list_mods(mods)
    elif args.command == "installed":
        list_installed(mods)
