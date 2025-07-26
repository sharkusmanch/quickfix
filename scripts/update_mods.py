import requests
import json
import os
import re
import unicodedata
import copy

BLOCKLIST = [
    "Lyall/BepInEx",
    "Lyall/BipedFix"
]

STEAM_SEARCH_API = "https://store.steampowered.com/api/storesearch/?term={}&l=english&cc=US"
API_TOKEN = os.environ.get("CODEBERG_TOKEN")
CODEBERG_API = "https://codeberg.org/api/v1"

def codeberg_get(url):
    headers = {}
    if API_TOKEN:
        headers["Authorization"] = f"token {API_TOKEN}"
    return requests.get(url, headers=headers, timeout=10)

def fetch_repos():
    repos = []
    page = 1
    while True:
        url = f"{CODEBERG_API}/users/Lyall/repos?page={page}&limit=100"
        response = codeberg_get(url)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos

def clean_game_title(title):
    if not title:
        return ""

    substitutions = {
        "’": "'", "‘": "'", "“": '"', "”": '"',
        "–": "-", "—": "-"
    }
    for bad, good in substitutions.items():
        title = title.replace(bad, good)

    title = unicodedata.normalize("NFKD", title)
    title = title.encode("ASCII", "ignore").decode("ASCII")
    title = re.sub(r"\s+", " ", title).strip()
    return title

def guess_game_from_repo(repo):
    description = repo.get("description", "").strip()
    if not description:
        return None

    match = re.search(r"for\s+(.+?)(?:\sthat|\sto|\sand|\.\s|$)", description, re.IGNORECASE)
    if match:
        search_term = match.group(1).strip()
    else:
        search_term = description.split("\n")[0].strip()
        search_term = re.sub(r"Fix|Patch|Tweak|Plugin|Mod", "", search_term, flags=re.IGNORECASE).strip()

    if not search_term:
        return None

    print(f"🔎 Attempting Steam search for: '{search_term}'...")

    try:
        steam_response = requests.get(STEAM_SEARCH_API.format(search_term), timeout=5)
        steam_response.raise_for_status()
        results = steam_response.json().get("items", [])
        if results:
            best_match = results[0]
            appid = best_match.get("id")
            print(f"✅ Found Steam AppID: {appid}")
            return appid
    except Exception as e:
        print(f"⚠️ Steam search failed for '{search_term}': {e}")

    return None

def load_existing_mods():
    if os.path.exists("mods.json"):
        with open("mods.json", "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def main():
    repos = fetch_repos()
    existing_mods = load_existing_mods()

    updated_mods = copy.deepcopy(existing_mods)
    added_mods = []
    updated_mods_ids = []

    print(f"🔍 Total repos fetched: {len(repos)}")
    for repo in repos:
        name = repo.get("name")
        full_name = f"Lyall/{name}"  # Codeberg format
        print(f"\n---\nProcessing repo: {full_name}")
        if any(bad.lower() == full_name.lower() for bad in BLOCKLIST):
            print(f"⏩ Skipped (blocklist): {full_name}")
            continue

        if "fix" in name.lower() or "tweak" in name.lower():
            print(f"✅ Detected as mod: {full_name}")
            mod_id = name

            if mod_id not in existing_mods:
                print(f"🆕 New mod detected: {mod_id}")
                appid = guess_game_from_repo(repo)
                updated_mods[mod_id] = {
                    "repo": full_name,
                    "config_files": [f"{name}.ini"],
                    "games": [{"steam_appid": appid}] if appid else []
                }
                added_mods.append(mod_id)
            else:
                print(f"✏️ Existing mod: {mod_id}")
                preserved_config_files = existing_mods[mod_id].get("config_files", [])
                preserved_games = existing_mods[mod_id].get("games", [])

                new_entry = {
                    "repo": full_name,
                    "config_files": preserved_config_files,
                    "games": preserved_games
                }

                # Only mark as updated if there's a real difference
                if new_entry != existing_mods[mod_id]:
                    print(f"✏️ Updated mod: {mod_id}")
                    updated_mods[mod_id] = new_entry
                    updated_mods_ids.append(mod_id)
        else:
            print(f"❌ Not detected as mod (name does not contain 'fix' or 'tweak'): {full_name}")

    # Write updated mods.json
    with open("mods.json", "w", encoding="utf-8") as f:
        json.dump(updated_mods, f, indent=2, ensure_ascii=False)

    # Write pull request body
    with open("pr_body.md", "w", encoding="utf-8") as f:
        f.write("### 🔄 Auto-refresh of `mods.json`\n\n")
        if added_mods:
            f.write("#### 🆕 New Mods Added:\n")
            for mod_id in added_mods:
                f.write(f"- [{mod_id}](https://codeberg.org/{updated_mods[mod_id]['repo']})\n")
                for game in updated_mods[mod_id]["games"]:
                    f.write(f"  - [Steam App {game['steam_appid']}](https://store.steampowered.com/app/{game['steam_appid']}/)\n")
            f.write("\n")
        if updated_mods_ids:
            f.write("#### ✏️ Existing Mods Updated:\n")
            for mod_id in updated_mods_ids:
                f.write(f"- [{mod_id}](https://codeberg.org/{updated_mods[mod_id]['repo']})\n")
                for game in updated_mods[mod_id]["games"]:
                    f.write(f"  - [Steam App {game['steam_appid']}](https://store.steampowered.com/app/{game['steam_appid']}/)\n")

    print("✅ mods.json updated successfully.")
    print("✅ pr_body.md generated for pull request.")

if __name__ == "__main__":
    main()
