import json
import os
import sys
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

def github_get(url):
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return requests.get(url, headers=headers, timeout=10)

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

        response = github_get(f"https://api.github.com/repos/{repo}")
        if response.status_code != 200:
            print(f"❌ {mod_id}: GitHub repo '{repo}' does not exist.")
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
