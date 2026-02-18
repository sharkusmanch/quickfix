import os
import re
import winreg

from quickfix.api import debug_print


def get_steam_root():
    """Read the Steam installation path from the Windows registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
        return steam_path
    except Exception as e:
        print(f"[WARN] Failed to read Steam path from registry: {e}")
        return None


def parse_libraryfolders(steam_root):
    """Parse libraryfolders.vdf and return a list of steamapps directories."""
    libraries = []
    libraryfolders_path = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
    if not os.path.exists(libraryfolders_path):
        return libraries

    try:
        with open(libraryfolders_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

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
    """Read the installdir value from a Steam appmanifest ACF file."""
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
    """Scan Steam libraries for a game's install path by appid."""
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
