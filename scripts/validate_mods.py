import json
import os
import sys
import requests
import unicodedata
import re

STEAM_APP_DETAILS = "https://store.steampowered.com/api/appdetails?appids={}"

def clean_game_title(title):
    if not title:
        return ""
    title = unicodedata.normalize("NFKD", title)
    title = title.encode("ASCII", "ignore").decode("ASCII")
    title = re.sub(r"\s+", " ", title).strip().lower()
    return title

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

        response = requests.get(f"https://api.github.com/repos/{repo}")
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
            title = game.get("name")
            if not appid or not title:
                print(f"❌ {mod_id}: each game must have a 'name' and 'steam_appid'.")
                sys.exit(1)

            print(f"  🔍 Verifying AppID {appid}...")

            try:
                steam_response = requests.get(STEAM_APP_DETAILS.format(appid), timeout=5)
                steam_data = steam_response.json().get(str(appid), {}).get("data", {})
                steam_name = steam_data.get("name", "")
                if not steam_name:
                    print(f"⚠️  Warning: Steam API returned no title for {appid}")
                elif clean_game_title(title) not in clean_game_title(steam_name):
                    print(f"❌ {mod_id}: game title mismatch for AppID {appid}:")
                    print(f"    mods.json = {title}")
                    print(f"    Steam     = {steam_name}")
                    sys.exit(1)
            except Exception as e:
                print(f"⚠️  Warning: Steam app lookup failed for {appid}: {e}")

    print("✅ All checks passed for mods.json!")

if __name__ == "__main__":
    validate_mods()
