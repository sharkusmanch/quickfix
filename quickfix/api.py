import os
import time

import requests

from quickfix import CODEBERG_API, DEBUG_MODE


def debug_print(message):
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")


def codeberg_get(url, retries=1):
    """Shared Codeberg API client with optional retry."""
    headers = {}
    token = os.environ.get("CODEBERG_TOKEN")
    if token:
        debug_print(f"Authenticated Codeberg request: {url}")
        headers["Authorization"] = f"token {token}"

    for attempt in range(retries):
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response
        elif attempt < retries - 1:
            print(f"[WARN] Request failed (attempt {attempt + 1}), retrying...")
            time.sleep(2 ** attempt)

    return response


def fetch_latest_mods_json():
    """Fetch the latest mods.json from the GitHub raw URL."""
    url = "https://raw.githubusercontent.com/sharkusmanch/quickfix/master/mods.json"
    print("[INFO] Fetching latest mods.json from GitHub...")
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def get_latest_release_info(repo):
    """Return (version, download_url, checksum_url) from a Codeberg repo's latest release."""
    url = f"{CODEBERG_API}/repos/{repo}/releases/latest"
    response = codeberg_get(url)

    if response.status_code == 200:
        release_data = response.json()
        version = release_data.get("tag_name", "unknown")
        attachments = release_data.get("assets", [])

        download_url = None
        checksum_url = None
        for asset in attachments:
            name = asset.get("name", "")
            url = asset.get("browser_download_url")
            if name.endswith(".zip"):
                download_url = url
            elif name.lower() in ("sha256sum.txt", "sha256sums.txt", "checksums.txt"):
                checksum_url = url

        if not download_url:
            print(f"[ERROR] No download URL found for the latest release of {repo}.")
            return None, None, None

        return version, download_url, checksum_url
    else:
        print(f"[ERROR] Could not fetch release info for {repo}.")
        return None, None, None


def get_steam_game_name(appid):
    """Look up the human-readable game name from the Steam Store API."""
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=us&l=en"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data[str(appid)]["success"]:
            return data[str(appid)]["data"]["name"]
    except Exception:
        pass
    return f"Steam App {appid}"
