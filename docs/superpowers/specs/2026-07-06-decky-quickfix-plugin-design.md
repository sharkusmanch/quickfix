# QuickFix Decky Plugin — Design

**Date:** 2026-07-06
**Status:** Approved (pending spec review)

## Overview

Bring QuickFix's job — installing, updating, and removing Lyall's PC game fixes — to SteamOS Gaming Mode via a Decky Loader plugin. The plugin reuses quickfix's `mods.json` catalog (extended with new auto-derived fields) and delegates the Proton-required `WINEDLLOVERRIDES` launch options to the "Launch Options" Decky plugin (Wurielle/decky-launch-options, "DLO") through its documented integration event.

Background: Lyall's fixes are ASI/BepInEx/MelonLoader payloads activated by a proxy DLL (`dsound.dll`, `winmm.dll`, `dinput8.dll`, `version.dll`, or `winhttp.dll`) dropped next to the game executable. Under Proton, Wine's builtin DLL wins by default, so every fix additionally requires the launch option `WINEDLLOVERRIDES="<dll>=n,b" %command%` or it silently never loads. Installing files AND registering that override are therefore both mandatory.

## Goals

- Install/update/uninstall Lyall fixes for installed Steam games from the Quick Access Menu.
- Register the correct `WINEDLLOVERRIDES` toggle with DLO after each install.
- Extend `mods.json` so the required metadata (proxy DLL, loader type, extraction subdirectory) is derived automatically by the existing refresh workflow.

## Non-goals (v1)

- INI config viewing/editing in Gaming Mode.
- Per-game library-page UI integration (route patching).
- Background/automatic update checks.
- Fixing the Windows CLI's extraction bug (the new catalog fields enable that as a follow-up).
- Decky store submission (off-store distribution via "Install from URL").

---

## Part 1 — Catalog v2 (changes in `sharkusmanch/quickfix`)

### Schema additions to `mods.json`

Per-mod (top level, alongside `repo` / `config_files` / `games` / `last_updated`):

| Field | Type | Meaning |
|---|---|---|
| `wine_dll_override` | string | Proxy DLL stem, e.g. `"dsound"`. The launch option is `WINEDLLOVERRIDES="<value>=n,b" %command%`. |
| `loader` | string | `"ual"` \| `"bepinex"` \| `"melonloader"`. Drives UX hints (BepInEx first boot is slow). |
| `derived_release` | string | Release tag the two fields above were derived from (idempotency marker). |

Per-game (inside each `games[]` entry, optional):

| Field | Type | Meaning |
|---|---|---|
| `install_subdir` | string | Path relative to the game install root where the zip contents must land (e.g. `"Sandfall/Binaries/Win64"` for ClairObscurFix). Omitted when extraction to the install root is correct. Per-game because DragonTweak's 8 appids each need a different subdir. |

### Derivation script

New `scripts/derive_mod_metadata.py`, run by the existing `refresh-mods.yml` workflow after `update_mods.py`:

1. For each mod whose latest release tag differs from `derived_release` (or whose fields are missing): download the latest release zip from Codeberg, list entries with `\` normalized to `/`.
2. `wine_dll_override` = basename stem of the bundled DLL whose name is in the known proxy set (`dsound`, `winmm`, `dinput8`, `version`, `winhttp`, plus the remaining Ultimate ASI Loader x64 names). The zip is the source of truth, not the README — the one known README/zip mismatch (GreatCircleFix) is resolved in the zip's favor. `dxgi` is never auto-selected (would conflict with DXVK); if only unexpected DLLs are found, leave the field unset and flag it.
3. `loader`: `BepInEx/` entry → `bepinex`; `MelonLoader/` entry → `melonloader`; any `.asi` → `ual`.
4. Flat-zip detection: if the zip has no directory structure and the mod has games without `install_subdir`, add a warning line to `pr_body.md` so it gets curated manually in the auto-refresh PR.
5. Write `derived_release`.

`install_subdir` itself is manually curated (never overwritten by the script). Seed values from research: ClairObscurFix `Sandfall/Binaries/Win64`, SMTVFix `Project/Binaries/Win64`, Octopath2Fix `Octopath_Traveler2/Binaries/Win64`, DQXISFix `Game/Binaries/Win64`, MGSDeltaFix `MGSDelta/Binaries/Win64`, SHfFix `SHf/Binaries/Win64`, CrossWorldsFix `UNION/Binaries/Win64`, DQ7RFix `DQ7R/Binaries/Win64`, LEGOBatmanLotDKFix `LEGOBatmanLotDK/Binaries/Win64`, AbsolumFix `x64.steam`, DragonTweak per-appid (e.g. `runtime/media` for Infinite Wealth). Note: these are relative to the game install root, whose top-level folder name is already known from the appmanifest, so stored subdirs must exclude the install root component; exact values verified during implementation.

`scripts/validate_mods.py` gains checks: `wine_dll_override` (when present) is in the known proxy set; `loader` in the allowed enum; `install_subdir` contains no `..` or leading `/`.

Windows `quickfix.py` ignores the new fields for now (unknown keys are already tolerated).

---

## Part 2 — Plugin repo `decky-lyall` (display name: "Lyall Fixes")

Based on `SteamDeckHomebrew/decky-plugin-template`: `api_version: 1`, `@decky/ui` + `@decky/api`, rollup via `@decky/rollup`, pnpm 9. **No `root` flag** — the `deck` user owns all Steam library paths, including SD cards. No compiled backend.

### Python backend (`main.py`, helpers in `py_modules/`)

Runs on Decky's frozen Python 3.11 (aiohttp + certifi available; no pip, no requests).

**Catalog:** fetch `https://raw.githubusercontent.com/sharkusmanch/quickfix/master/mods.json` on load and on manual refresh; cache in `DECKY_PLUGIN_SETTINGS_DIR/mods.json` for offline use. Skip mods lacking `wine_dll_override` (not yet derivable).

**Game detection** (port of quickfix.py minus winreg): probe Steam roots `~/.local/share/Steam`, `~/.steam/steam`, `~/.steam/root`; parse `steamapps/libraryfolders.vdf` for library paths (this covers SD card/USB libraries — never hardcode `/run/media`); parse `appmanifest_<appid>.acf` for `installdir` → `<library>/steamapps/common/<installdir>`. Regex line-parsing as today; no vendored `vdf` package needed.

**Download:** Codeberg API `GET /repos/{repo}/releases/latest`, pick the `.zip` asset; download via aiohttp with `ssl.create_default_context(cafile=certifi.where())` into `DECKY_PLUGIN_RUNTIME_DIR/downloads/`.

**Extractor (hardened, new):**
- Normalize `\` → `/` in every zip entry name (SyberiaTWBFix's current release uses backslash separators, which stock `zipfile.extractall` turns into junk files on Linux).
- Zip-slip guard: reject entries resolving outside the target directory.
- Skip the `EXTRACT_TO_GAME_FOLDER` marker file.
- Target directory: `install_path + install_subdir` when the game entry has one; otherwise, if the zip is flat (no directories) and the install root lacks the game's shipping exe, locate `**/Binaries/Win64/*-Shipping.exe` (Unreal heuristic) and extract there; else extract to the install root.
- Merge into existing directories case-insensitively (ext4 is case-sensitive; a case-mismatched duplicate tree means the DLL never loads).
- Before overwriting an existing file, copy it to `DECKY_PLUGIN_RUNTIME_DIR/backups/<appid>-<mod_id>/`.

**Install manifest:** `DECKY_PLUGIN_RUNTIME_DIR/installs/<appid>-<mod_id>.json` with `{mod_id, appid, version, install_path, target_dir, files[], backed_up_files[], wine_dll_override, installed_at}`. Status is re-derived from disk (manifest + files present), so it survives reinstall/reboot. Uninstall deletes listed files, restores backups, removes the manifest.

**Safety:** refuse install/uninstall while the game is running (scan `/proc` cmdlines for the install path).

**Callables** (all `async` methods on `Plugin`):
- `get_state()` → `{catalog_loaded, games: [{appid, mod_id, install_path, installed_version, latest_version, wine_dll_override, loader, status}]}` where `status` ∈ `not_installed | installed | update_available | unknown`. Only games present both on disk and in the catalog.
- `refresh()` → re-fetch catalog and latest release versions.
- `install(mod_id, appid)` / `uninstall(mod_id, appid)` → `{ok, error?, wine_dll_override?}`.
- Progress: `decky.emit("qf_progress", mod_id, appid, phase, pct)` for download/extract phases.

Version checks call Codeberg per mod; do them lazily (on QAM open / explicit refresh), not on a timer.

### Frontend (`src/`)

- `index.tsx`: `definePlugin`; on mount, detect `(window as any).hasDeckyLaunchOptions`.
- **QAM panel:** list of detected games with available fixes — display name via `appStore.GetAppOverviewByAppID(appid)` (retry-wrapped), status line (`Installed 0.0.15 · 0.0.16 available`), context-aware button (Install / Update / Uninstall), refresh button, `toaster.toast` on completion/failure, progress from `qf_progress` events. For BepInEx mods, the post-install toast warns that first boot takes minutes.
- **DLO required:** if `hasDeckyLaunchOptions` is falsy, the panel shows an explanation ("Lyall Fixes needs the 'Launch Options' plugin from the Decky store to activate fixes under Proton") and install buttons are disabled. No direct `SetAppLaunchOptions` writes in v1.
- **DLO registration:** after a successful install, dispatch:
  ```ts
  window.dispatchEvent(new CustomEvent('dlo-add-launch-options', {
    detail: [{
      id: `lyall-${modId}`,             // stable → re-dispatch upserts
      group: 'Lyall Fixes',
      name: `${modId} (${dll} override)`,
      on: `WINEDLLOVERRIDES="${dll}=n,b"`,  // env-only; DLO merges WINEDLLOVERRIDES across options with ';'
      off: '',
      enableGlobally: false,
    }]
  }));
  ```
  DLO shows its confirm dialog; a follow-up toast tells the user to enable the toggle on the game's page. Uninstall cannot remove DLO options (no such event exists); the toast tells the user to disable the toggle. Upstream feature request to file with Wurielle: a per-app enable/remove event.

### Error handling

- Network failures: fall back to cached catalog; per-mod version check failures degrade that row to `unknown` with a retry affordance.
- Extraction failure mid-way: restore backups and delete files written so far (track as we go), report via toast + `decky.logger`.
- All backend exceptions bubble to the frontend as JS errors — every callable invocation is try/caught in the API layer and surfaced as a toast.

### Repo layout, CI, distribution

- Template-derived layout: `main.py`, `py_modules/lyall_core/` (detection, download, extract, manifest — unit-testable pure Python), `src/`, `plugin.json` (`flags: []`), `package.json`, `defaults/`.
- GitHub Actions: lint + pytest for `py_modules/lyall_core` (fixture zips: flat, pathed, backslash-entries, zip-slip), `pnpm build`, decky CLI zip build; on tag push, attach the zip to a GitHub release.
- Install URL for users: `https://github.com/sharkusmanch/decky-lyall/releases/latest/download/decky-lyall.zip` via Decky Settings → Developer → Install from URL.
- Dev loop: rsync to `deck@<ip>:~/homebrew/plugins` + `systemctl restart plugin_loader`; CEF debugging via `chrome://inspect` → `<deck-ip>:8081`.

### Testing

- Unit tests (CI, no Deck): extractor rules against fixture zips; manifest/uninstall round-trip in a temp dir; vdf/acf parsing against captured Deck fixtures.
- On-device smoke test (manual): one mod per shape — ClairObscurFix (flat + subdir + dsound), FF7RebirthFix (pathed + dsound), a winmm mod (e.g. MGSVFix), a BepInEx mod (e.g. RaidouFix) — verifying files land next to the shipping exe, DLO import appears, and the fix loads in-game with the toggle on.

## Risks / notes

- `SteamClient`/`appStore` internals are unversioned Valve APIs; the blast radius is limited to display names (worst case: show appids).
- DLO's store version lags GitHub; the integration event exists since v1.8 but field-level compatibility (e.g. `priority`) should be tested against the store build.
- Steam game updates can break offset-based fixes until Lyall updates them — the update flow covers recovery, and this is upstream of us.
- Games on NTFS external drives are a general Proton problem, unrelated to the plugin.

## Follow-ups (explicitly out of v1)

1. Use `install_subdir` in Windows `quickfix.py` (fixes the current Layout-B bug where the proxy DLL lands next to the launcher stub).
2. Upstream DLO feature request: programmatic per-app option enable/remove.
3. Optional `quickfix-recipes.json` for DLO's Recipes companion plugin as a code-free alternative channel.
4. INI config editor, per-game page integration, background update checks.
