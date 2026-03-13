import json
import os
import sys
import time

# Allow importing from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quickfix.api import codeberg_get
from quickfix import CODEBERG_API


def validate_mods():
    mods_path = "mods.json"
    if not os.path.exists(mods_path):
        print("mods.json not found.")
        sys.exit(1)

    try:
        with open(mods_path, "r", encoding="utf-8") as f:
            mods = json.load(f)
    except Exception as e:
        print(f"Failed to parse mods.json: {e}")
        sys.exit(1)

    seen_appids = {}  # appid -> list of mod_ids (for duplicate detection)

    for mod_id, mod in mods.items():
        print(f"Checking mod: {mod_id}")

        repo = mod.get("repo")
        if not repo:
            print(f"{mod_id}: missing 'repo' field.")
            sys.exit(1)

        response = codeberg_get(f"{CODEBERG_API}/repos/{repo}", retries=3)
        if response.status_code != 200:
            print(f"{mod_id}: Codeberg repo '{repo}' does not exist.")
            sys.exit(1)

        config_files = mod.get("config_files", [])
        if not config_files:
            print(f"{mod_id}: missing 'config_files'.")
            sys.exit(1)

        games = mod.get("games", [])
        if not games:
            print(f"[WARN] {mod_id}: empty 'games' list. Skipping game validation.")
            continue

        for game in games:
            appid = game.get("steam_appid")
            if not appid or not isinstance(appid, int):
                print(f"{mod_id}: invalid or missing 'steam_appid'.")
                sys.exit(1)
            seen_appids.setdefault(appid, []).append(mod_id)

    # Post-loop: warn about duplicate appids (not an error - legitimate for DragonTweak etc.)
    for appid, mod_ids in seen_appids.items():
        if len(mod_ids) > 1:
            print(f"[WARN] Steam appid {appid} is shared by: {', '.join(mod_ids)}")

    print("All checks passed for mods.json!")


if __name__ == "__main__":
    validate_mods()
