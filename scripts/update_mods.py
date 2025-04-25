import requests
import json
import os
import re

BLOCKLIST = [
    "Lyall/BepInEx",
    "Lyall/BipedFix"
]

STEAM_SEARCH_API = "https://store.steampowered.com/api/storesearch/?term={}&l=english&cc=US"

def fetch_repos():
    response = requests.get("https://api.github.com/users/Lyall/repos?per_page=100")
    response.raise_for_status()
    return response.json()

def load_existing_mods():
    if os.path.exists("mods.json"):
        with open("mods.json", "r") as f:
            return json.load(f)
    else:
        return {}

def guess_game_from_repo(repo):
    description = repo.get("description", "").strip()
    if not description:
        return None, None

    # Use first line of description or smartly guess a title
    search_term = description.split("\n")[0].strip()
    search_term = re.sub(r"Fix|Patch|Tweak", "", search_term, flags=re.IGNORECASE).strip()

    if not search_term:
        return None, None

    print(f"🔎 Attempting Steam search for: '{search_term}'...")

    try:
        steam_response = requests.get(STEAM_SEARCH_API.format(search_term), timeout=5)
        steam_response.raise_for_status()
        results = steam_response.json().get("items", [])
        if results:
            best_match = results[0]
            appid = best_match.get("id")
            name = best_match.get("name")
            print(f"✅ Found Steam match: {name} (AppID: {appid})")
            return appid, name
        else:
            print(f"⚠️ No Steam results for '{search_term}'.")
    except Exception as e:
        print(f"⚠️ Steam search failed for '{search_term}': {e}")

    return None, None

def main():
    repos = fetch_repos()
    existing_mods = load_existing_mods()

    updated_mods = existing_mods.copy()

    for repo in repos:
        name = repo["name"]
        full_name = repo["full_name"]

        if any(bad.lower() == full_name.lower() for bad in BLOCKLIST):
            continue

        if "fix" in name.lower() or "tweak" in name.lower():
            mod_id = name

            if mod_id in existing_mods:
                # Preserve existing fields
                preserved_config_files = existing_mods[mod_id].get("config_files", [])
                preserved_games = existing_mods[mod_id].get("games", [])

                updated_mods[mod_id] = {
                    "repo": full_name,
                    "config_files": preserved_config_files,
                    "games": preserved_games
                }
            else:
                # New mod
                appid, game_name = guess_game_from_repo(repo)
                updated_mods[mod_id] = {
                    "repo": full_name,
                    "config_files": [f"{name}.ini"],
                    "games": [{
                        "name": game_name,
                        "steam_appid": appid
                    }] if appid and game_name else []
                }

    with open("mods.json", "w") as f:
        json.dump(updated_mods, f, indent=2)

    print("✅ mods.json updated successfully, preserving existing entries.")

if __name__ == "__main__":
    main()
