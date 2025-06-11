import json
import os
import sys
import time
import requests

API_TOKEN = os.environ.get("CODEBERG_TOKEN")
CODEBERG_API = "https://codeberg.org/api/v1"

def codeberg_get(url, retries=3):
    headers = {}
    if API_TOKEN:
        headers["Authorization"] = f"token {API_TOKEN}"
        print(f"🔒 Authenticated Codeberg request: {url}")
    else:
        print(f"🌐 Public Codeberg request: {url}")

    for attempt in range(retries):
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response
        elif attempt < retries - 1:
            print(f"⚠️ Request failed (attempt {attempt + 1}), retrying...")
            time.sleep(2 ** attempt)
    response.raise_for_status()

def validate_mods():
    mods_path = "mods.json"
    if not os.path.exists(mods_path):
        print("❌ mods.json not found.")
        sys.exit(1)

    try:
        with open(mods_path, "r", encoding="utf-8") as f:
            mods = json.load(f)
    except Exception as e:
        print(f"❌ Failed to parse mods.json: {e}")
        sys.exit(1)

    for mod_id, mod in mods.items():
        print(f"🔎 Checking mod: {mod_id}")

        repo = mod.get("repo")
        if not repo:
            print(f"❌ {mod_id}: missing 'repo' field.")
            sys.exit(1)

        response = codeberg_get(f"{CODEBERG_API}/repos/{repo}")
        if response.status_code != 200:
            print(f"❌ {mod_id}: Codeberg repo '{repo}' does not exist.")
            sys.exit(1)

        config_files = mod.get("config_files", [])
        if not config_files:
            print(f"❌ {mod_id}: missing 'config_files'.")
            sys.exit(1)

        games = mod.get("games", [])
        if not games:
            print(f"❌ {mod_id}: missing or empty 'games' list.")
            sys.exit(1)

        for game in games:
            appid = game.get("steam_appid")
            if not appid or not isinstance(appid, int):
                print(f"❌ {mod_id}: invalid or missing 'steam_appid'.")
                sys.exit(1)

    print("✅ All checks passed for mods.json!")

if __name__ == "__main__":
    validate_mods()
