import requests
import json
import os
import re
import unicodedata

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
        with open("mods.json", "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def clean_game_title(title):
    if not title:
        return ""
    title = unicodedata.normalize("NFKD", title)
    title = title.encode("ASCII", "ignore").decode("ASCII")
    title = re.sub(r"\s+", " ", title).strip()
    return title

def guess_game_from_repo(repo):
    description = repo.get("description", "").strip()
    if not description:
        return None, None

    match = re.search(r"for\s+(.+?)(?:\sthat|\sto|\sand|\.\s|$)", description, re.IGNORECASE)
    if match:
        search_term = match.group(1).strip()
    else:
        search_term = description.split("\n")[0].strip()
        search_term = re.sub(r"Fix|Patch|Tweak|Plugin|Mod", "", search_term, flags=re.IGNORECASE).strip()

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
            name = clean_game_title(best_match.get("name", ""))
            print(f"✅ Found Steam match: {name} (AppID: {appid})")
            return appid, name
    except Exception as e:
        print(f"⚠️ Steam search failed for '{search_term}': {e}")

    return None, None

def main():
    repos = fetch_repos()
    existing_mods = load_existing_mods()

    updated_mods = existing_mods.copy()
    added_mods = []
    updated_mod_ids = []

    for repo in repos:
        name = repo["name"]
        full_name = repo["full_name"]

        if any(bad.lower() == full_name.lower() for bad in BLOCKLIST):
            continue

        if "fix" in name.lower() or "tweak" in name.lower():
            mod_id = name

            if mod_id in existing_mods:
                preserved_config_files = existing_mods[mod_id].get("config_files", [])
                preserved_games = existing_mods[mod_id].get("games", [])

                updated_mods[mod_id] = {
                    "repo": full_name,
                    "config_files": preserved_config_files,
                    "games": preserved_games
                }
                updated_mod_ids.append(mod_id)
            else:
                appid, game_name = guess_game_from_repo(repo)
                updated_mods[mod_id] = {
                    "repo": full_name,
                    "config_files": [f"{name}.ini"],
                    "games": [{
                        "name": game_name,
                        "steam_appid": appid
                    }] if appid and game_name else []
                }
                added_mods.append(mod_id)

    with open("mods.json", "w", encoding="utf-8") as f:
        json.dump(updated_mods, f, indent=2, ensure_ascii=False)

    with open("pr_body.md", "w", encoding="utf-8") as f:
        f.write("### 🔄 Auto-refresh of `mods.json`\n\n")
        if added_mods:
            f.write("#### 🆕 New Mods Added:\n")
            for mod_id in added_mods:
                f.write(f"- [{mod_id}](https://github.com/{updated_mods[mod_id]['repo']})\n")
            f.write("\n")
        if updated_mod_ids:
            f.write("#### ✏️ Existing Mods Updated:\n")
            for mod_id in updated_mod_ids:
                f.write(f"- [{mod_id}](https://github.com/{updated_mods[mod_id]['repo']})\n")

    print("✅ mods.json updated successfully.")
    print("✅ pr_body.md generated for pull request.")

if __name__ == "__main__":
    main()
