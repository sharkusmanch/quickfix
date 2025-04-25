import requests
import json
import os

BLOCKLIST = [
    "Lyall/BepInEx",
    "Lyall/BipedFix"
]

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
                # Preserve existing config_files and games
                preserved_config_files = existing_mods[mod_id].get("config_files", [])
                preserved_games = existing_mods[mod_id].get("games", [])

                updated_mods[mod_id] = {
                    "repo": full_name,
                    "config_files": preserved_config_files,
                    "games": preserved_games
                }
            else:
                # New mod
                updated_mods[mod_id] = {
                    "repo": full_name,
                    "config_files": [f"{name}.ini"],
                    "games": []  # To be filled manually later
                }

    with open("mods.json", "w") as f:
        json.dump(updated_mods, f, indent=2)

    print("✅ mods.json updated successfully, preserving existing entries.")

if __name__ == "__main__":
    main()
