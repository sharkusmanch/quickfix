import json
import os
import sys
import requests

STEAM_API_APP_DETAILS = "https://store.steampowered.com/api/appdetails?appids={}"

def validate_mods():
    mods_path = "mods.json"
    if not os.path.exists(mods_path):
        print("❌ mods.json not found.")
        sys.exit(1)

    # 1. Validate JSON is valid
    try:
        with open(mods_path, "r") as f:
            mods = json.load(f)
    except Exception as e:
        print(f"❌ Failed to parse mods.json: {e}")
        sys.exit(1)

    # 2. Check each mod entry
    for mod_id, mod in mods.items():
        print(f"🔎 Checking mod: {mod_id}")

        # Repo must exist
        repo = mod.get("repo")
        if not repo:
            print(f"❌ {mod_id}: missing 'repo' field.")
            sys.exit(1)

        response = requests.get(f"https://api.github.com/repos/{repo}")
        if response.status_code != 200:
            print(f"❌ {mod_id}: GitHub repo '{repo}' does not exist or is not accessible.")
            sys.exit(1)

        # config_files must be provided
        config_files = mod.get("config_files", [])
        if not config_files:
            print(f"❌ {mod_id}: missing 'config_files' field.")
            sys.exit(1)

        # games list must exist and not be empty
        games = mod.get("games", [])
        if not games:
            print(f"❌ {mod_id}: missing or empty 'games' list.")
            sys.exit(1)

        # 3. Check each game's steam appid
        for game in games:
            appid = game.get("steam_appid")
            title = game.get("name")
            if not appid or not title:
                print(f"❌ {mod_id}: each game must have a 'name' and 'steam_appid'.")
                sys.exit(1)

            print(f"  🔎 Verifying Steam AppID {appid}...")

            try:
                steam_response = requests.get(STEAM_API_APP_DETAILS.format(appid), timeout=5)
                steam_data = steam_response.json().get(str(appid), {}).get("data", {})
                steam_name = steam_data.get("name", "").strip()

                if not steam_name:
                    print(f"⚠️ Warning: Steam API did not return a name for AppID {appid}.")
                else:
                    # Compare game title from mods.json to Steam title
                    if title.lower() not in steam_name.lower():
                        print(f"❌ {mod_id}: Game title mismatch for AppID {appid}: '{title}' vs Steam '{steam_name}'")
                        sys.exit(1)

            except Exception as e:
                print(f"⚠️ Warning: Failed to validate Steam AppID {appid}: {e}")

    print("✅ All mods.json checks passed successfully!")

if __name__ == "__main__":
    validate_mods()
