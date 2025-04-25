import requests
import json

BLOCKLIST = [
    "Lyall/BepInEx",
    "Lyall/BipedFix"
]

def main():
    response = requests.get("https://api.github.com/users/Lyall/repos?per_page=100")
    response.raise_for_status()
    repos = response.json()

    mods = {}

    for repo in repos:
        name = repo["name"]
        full_name = repo["full_name"]

        if any(bad in full_name for bad in BLOCKLIST):
            continue

        if "fix" in name.lower() or "tweak" in name.lower():
            mod_id = name
            mods[mod_id] = {
                "repo": full_name,
                "config_files": [f"{name}.ini"],
                "games": []  # games must be filled manually for now
            }

    with open("mods.json", "w") as f:
        json.dump(mods, f, indent=2)

if __name__ == "__main__":
    main()
