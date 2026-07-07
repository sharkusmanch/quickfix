import argparse
import hashlib
import io
import json
import os
import zipfile

import requests

CODEBERG_API = "https://codeberg.org/api/v1"

# UAL x64 proxy names Lyall's fixes can ship. dxgi is deliberately excluded:
# auto-overriding it would break DXVK.
KNOWN_PROXY_DLLS = frozenset({
    "dsound", "winmm", "dinput8", "version", "winhttp",
    "wininet", "d3d9", "d3d10", "d3d11", "d3d12",
    "xinput1_1", "xinput1_2", "xinput1_3", "xinput1_4",
    "xinput9_1_0", "xinputuap", "binkw64", "bink2w64",
})

DERIVED_FIELDS = ("wine_dll_override", "loader", "zip_layout", "download_url", "sha256", "size")


def analyze_zip(names):
    """Derive {wine_dll_override, loader, zip_layout} from zip entry names."""
    norm = [n.replace("\\", "/").lstrip("/") for n in names]
    payload = [n for n in norm
               if n and not n.endswith("/")
               and os.path.basename(n) != "EXTRACT_TO_GAME_FOLDER"]

    top_dirs = {n.split("/", 1)[0] for n in payload if "/" in n}
    if "BepInEx" in top_dirs:
        loader = "bepinex"
    elif "MelonLoader" in top_dirs:
        loader = "melonloader"
    else:
        loader = "ual"

    candidates = []
    for n in payload:
        base = os.path.basename(n).lower()
        if base.endswith(".dll") and base[:-4] in KNOWN_PROXY_DLLS:
            candidates.append((n.count("/"), base[:-4]))

    override = None
    if candidates:
        min_depth = min(depth for depth, _ in candidates)
        at_min = {stem for depth, stem in candidates if depth == min_depth}
        if len(at_min) == 1:
            override = at_min.pop()

    zip_layout = "pathed" if any("/" in n for n in payload) else "flat"
    return {"wine_dll_override": override, "loader": loader, "zip_layout": zip_layout}


def codeberg_get(url):
    headers = {}
    token = os.environ.get("CODEBERG_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return requests.get(url, headers=headers, timeout=15)


def get_latest_zip_asset(repo):
    """Return {'tag', 'url'} for the latest release's .zip asset, or None."""
    resp = codeberg_get(f"{CODEBERG_API}/repos/{repo}/releases/latest")
    if resp.status_code != 200:
        return None
    data = resp.json()
    for asset in data.get("assets", []):
        if asset.get("name", "").endswith(".zip"):
            return {"tag": data.get("tag_name", ""), "url": asset["browser_download_url"]}
    return None


def download(url):
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def needs_derivation(mod, tag):
    if mod.get("derived_release") != tag:
        return True
    return not all(mod.get(f) for f in DERIVED_FIELDS)


def derive_mod(mod, release, blob):
    """Derive and set metadata fields on mod, in place. install_subdir is never touched."""
    meta = analyze_zip(zipfile.ZipFile(io.BytesIO(blob)).namelist())
    mod["loader"] = meta["loader"]
    mod["zip_layout"] = meta["zip_layout"]
    if meta["wine_dll_override"]:
        mod["wine_dll_override"] = meta["wine_dll_override"]
    mod["download_url"] = release["url"]
    mod["sha256"] = hashlib.sha256(blob).hexdigest()
    mod["size"] = len(blob)
    mod["derived_release"] = release["tag"]


def collect_warnings(mods):
    warnings = []
    seen_appids = {}
    for mod_id, mod in mods.items():
        if not mod.get("wine_dll_override"):
            warnings.append(f"`{mod_id}`: no `wine_dll_override` derived — invisible on Deck until set")
        if not mod.get("games"):
            warnings.append(f"`{mod_id}`: empty `games[]` — needs a Steam appid")
        for game in mod.get("games", []):
            appid = game.get("steam_appid")
            # install_subdir "." is the explicit "extract to install root" marker
            # (README-verified); absence means the target dir is unknown.
            if mod.get("zip_layout") == "flat" and not game.get("install_subdir"):
                warnings.append(f"`{mod_id}`: flat zip but appid {appid} has no `install_subdir` — installs blocked on Deck")
            if appid in seen_appids and seen_appids[appid] != mod_id:
                warnings.append(f"appid {appid} claimed by both `{seen_appids[appid]}` and `{mod_id}`")
            seen_appids.setdefault(appid, mod_id)
    return warnings


def main():
    parser = argparse.ArgumentParser(description="Derive mod metadata from release zips")
    parser.add_argument("--only", nargs="*", help="Limit to these mod ids (for local smoke runs)")
    args = parser.parse_args()

    with open("mods.json", "r", encoding="utf-8") as f:
        mods = json.load(f)

    changed = False
    for mod_id, mod in mods.items():
        if args.only and mod_id not in args.only:
            continue
        release = get_latest_zip_asset(mod["repo"])
        if release is None:
            print(f"⚠️ {mod_id}: no release with a .zip asset")
            continue
        if needs_derivation(mod, release["tag"]):
            print(f"🔬 Deriving {mod_id} @ {release['tag']}")
            try:
                blob = download(release["url"])
            except Exception as e:
                print(f"⚠️ {mod_id}: download failed: {e}")
                continue
            derive_mod(mod, release, blob)
            changed = True
        else:
            print(f"✅ {mod_id}: up to date ({release['tag']})")

    if changed:
        with open("mods.json", "w", encoding="utf-8") as f:
            json.dump(mods, f, indent=2, ensure_ascii=False)
        print("✅ mods.json updated with derived metadata.")

    scope = {k: mods[k] for k in args.only} if args.only else mods
    warnings = collect_warnings(scope)
    if warnings:
        with open("pr_body.md", "a", encoding="utf-8") as f:
            f.write("\n### ⚠️ Curation needed\n\n")
            for w in warnings:
                f.write(f"- {w}\n")
        print(f"⚠️ {len(warnings)} curation warnings appended to pr_body.md")


if __name__ == "__main__":
    main()
