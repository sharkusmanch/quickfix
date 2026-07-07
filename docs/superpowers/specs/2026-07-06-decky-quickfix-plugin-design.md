# QuickFix Decky Plugin — Design

**Date:** 2026-07-06 (rev 2, after multi-agent review)
**Status:** Approved design; rev 2 amendments pending user review

## Overview

Bring QuickFix's job — installing, updating, and removing Lyall's PC game fixes — to SteamOS Gaming Mode via a Decky Loader plugin. The plugin reuses quickfix's `mods.json` catalog (extended with new auto-derived fields) and delegates the Proton-required `WINEDLLOVERRIDES` launch options to the "Launch Options" Decky plugin (Wurielle/decky-launch-options, "DLO") through its documented integration event.

Background: Lyall's fixes are ASI/BepInEx/MelonLoader payloads activated by a proxy DLL (`dsound.dll`, `winmm.dll`, `dinput8.dll`, `version.dll`, or `winhttp.dll`) dropped next to the game executable. Under Proton, Wine's builtin DLL wins by default, so every fix additionally requires the launch option `WINEDLLOVERRIDES="<dll>=n,b" %command%` or it silently never loads. Installing files AND registering that override are therefore both mandatory.

## Goals

- Install/update/uninstall Lyall fixes for installed Steam games from the Quick Access Menu.
- Register the correct `WINEDLLOVERRIDES` toggle with DLO after each install, with visible activation state.
- Extend `mods.json` so the required metadata (proxy DLL, loader type, extraction layout, pinned asset hash) is derived automatically by the existing refresh workflow.

## Non-goals (v1)

- INI config viewing/editing in Gaming Mode.
- Per-game library-page UI integration (route patching).
- Background/automatic update checks.
- Programmatic launch-option writes (`SteamClient.Apps.SetAppLaunchOptions`) — DLO or manual copy only.
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
| `zip_layout` | string | `"pathed"` (zip embeds relative paths from install root) \| `"flat"` (payload files at zip root). Determines extraction target selection. |
| `derived_release` | string | Release tag the derived fields were computed from. **Doubles as the plugin's `latest_version` source** — the plugin makes zero Codeberg API calls for version checks. |
| `download_url` | string | Exact `browser_download_url` of the .zip asset the derivation script inspected. |
| `sha256` | string | Lowercase hex SHA-256 of that asset. Installs verify against this before extraction. |
| `size` | int | Asset byte size (cheap pre-check + download-progress denominator). |

Pinning rationale (review finding, critical): Forgejo release assets are mutable without a tag change, so installing unpinned "latest" assets would let a compromised upstream account deliver arbitrary code, and `derived_release` idempotency would never re-inspect a swapped asset. Pinning also eliminates metadata/payload version skew by construction: the plugin installs exactly the zip the derivation script inspected. Precedent: Decky-Framegen and decky-16x10-fixes both pin sha256.

Per-game (inside each `games[]` entry, optional):

| Field | Type | Meaning |
|---|---|---|
| `install_subdir` | string | Path relative to the game install root where a **flat** zip's contents must land (e.g. `"Sandfall/Binaries/Win64"` for ClairObscurFix). Required for flat-layout mods; per-game because DragonTweak's 8 appids each need a different subdir. |

Constraint: `mods.json` is a flat dict whose every top-level key the Windows CLI treats as a mod (`list-mods` iterates `mods.keys()`), so **no top-level metadata/version key can be added** until the CLI is updated. Schema versioning lives in the plugin's install manifests instead.

### Derivation script

New `scripts/derive_mod_metadata.py`, run by the existing `refresh-mods.yml` workflow after `update_mods.py`:

1. For each mod whose latest release tag differs from `derived_release` (or whose derived fields are missing): download the latest release zip from Codeberg, list entries with `\` normalized to `/`.
2. `wine_dll_override` = basename stem of the bundled DLL whose name is in the known proxy set (`dsound`, `winmm`, `dinput8`, `version`, `winhttp`, plus the remaining Ultimate ASI Loader x64 names). The zip is the source of truth, not the README — the one known README/zip mismatch (GreatCircleFix) is resolved in the zip's favor. `dxgi` is never auto-selected (would conflict with DXVK); if only unexpected DLLs are found, leave the field unset and flag it.
3. `loader`: `BepInEx/` entry → `bepinex`; `MelonLoader/` entry → `melonloader`; any `.asi` → `ual`.
4. `zip_layout`: `pathed` if payload entries carry directory paths from the install root; `flat` otherwise.
5. Record `download_url`, `sha256` (of the downloaded bytes), `size`, and `derived_release`. `derived_release` is written on every run for every mod with a resolvable release, including mods whose other fields were flagged rather than derived.
6. Append warnings to `pr_body.md` for human curation in the auto-refresh PR: flat-layout mods with any game entry missing `install_subdir`; mods where `wine_dll_override` could not be derived; mods with empty `games[]`; appids claimed by more than one mod.

**Prerequisite fix in `scripts/update_mods.py` (review finding, critical):** it currently rebuilds every existing entry with exactly four keys (`repo`, `config_files`, `games`, `last_updated`) and replaces the entry whenever the rebuilt dict differs — which would strip all derived fields on every 6-hour run and silently force `derive_mod_metadata.py` to re-download all ~100 zips forever. Change it to start `new_entry` from a copy of the existing entry and update only the four keys it owns, preserving unknown fields.

`install_subdir` is manually curated (never overwritten by the script). Seed values from research: ClairObscurFix `Sandfall/Binaries/Win64`, SMTVFix `Project/Binaries/Win64`, Octopath2Fix `Octopath_Traveler2/Binaries/Win64`, DQXISFix `Game/Binaries/Win64`, MGSDeltaFix `MGSDelta/Binaries/Win64`, SHfFix `SHf/Binaries/Win64`, CrossWorldsFix `UNION/Binaries/Win64`, DQ7RFix `DQ7R/Binaries/Win64`, LEGOBatmanLotDKFix `LEGOBatmanLotDK/Binaries/Win64`, AbsolumFix `x64.steam`, DragonTweak per-appid (e.g. `runtime/media` for Infinite Wealth). Paths are relative to the game install root (exclude the install-root folder itself); exact values verified during implementation.

Known catalog data fixes to make alongside: `OctopathFix` currently lists appid 1971650, which belongs to Octopath Traveler II and is also claimed by `Octopath2Fix` (bad auto-guess); correct it to Octopath Traveler 1's appid. `DOAXVVPrismFix` and `NoSleepForKanameDateFix` have empty `games[]`.

`scripts/validate_mods.py` gains checks: `wine_dll_override` (when present) in the known proxy set; `loader` and `zip_layout` in their enums; `install_subdir` contains no `..`, no leading `/`; `sha256` matches `^[0-9a-f]{64}$`; `download_url` is https on codeberg.org; `size` positive int; all pinning fields present whenever `derived_release` is set; warn on appids claimed by multiple mods and on empty `games[]`.

Windows `quickfix.py` ignores the new fields for now (unknown keys are tolerated at read time; the update_mods.py fix above makes them survive refresh).

---

## Part 2 — Plugin repo `decky-lyall` (display name: "Lyall Fixes")

Based on `SteamDeckHomebrew/decky-plugin-template`: `api_version: 1`, `@decky/ui` + `@decky/api`, rollup via `@decky/rollup`, pnpm 9. **No `root` flag** — the `deck` user owns all Steam library paths, including SD cards. No compiled backend.

### Python backend (`main.py`, helpers in `py_modules/lyall_core/`)

Runs on Decky's frozen Python 3.11 (aiohttp + certifi available; no pip, no requests).

**Catalog:** fetch `https://raw.githubusercontent.com/sharkusmanch/quickfix/master/mods.json` on load and on `refresh()`; cache in `DECKY_PLUGIN_SETTINGS_DIR/mods.json` (with fetch timestamp) for offline use. **Plugin-side validation (defense in depth — the catalog is remote input):** mod ids must match `^[A-Za-z0-9._-]+$` (they become path components); `wine_dll_override` must be in the plugin's own proxy-DLL allowlist (it is interpolated into the DLO `on` string, which DLO shlex-parses and executes); `install_subdir` must be relative with no `..` segments; `download_url` must be https on codeberg.org; appids must be ints. Entries failing validation, or lacking `wine_dll_override`/`sha256`/`download_url`, are skipped.

**Game detection** (port of quickfix.py minus winreg): probe Steam roots `~/.local/share/Steam`, `~/.steam/steam`, `~/.steam/root`; parse `steamapps/libraryfolders.vdf` for library paths (this covers SD card/USB libraries — never hardcode `/run/media`); parse `appmanifest_<appid>.acf` for `installdir` → `<library>/steamapps/common/<installdir>`. Regex line-parsing as today; no vendored `vdf` package needed.

**Download:** always the catalog-pinned `download_url` (never `releases/latest`), via aiohttp with `ssl.create_default_context(cafile=certifi.where())`, streamed in chunks to `DECKY_PLUGIN_RUNTIME_DIR/downloads/<mod_id>-<tag>.zip` — the local filename is generated locally (mod_id from our validated catalog; tag validated against `^[A-Za-z0-9._-]+$`); the remote asset name is never used as a path component. SHA-256 is computed as bytes arrive; abort if the byte count exceeds the catalog `size`. Before extraction, the hash must equal the catalog `sha256`; on mismatch, delete the file and fail with a distinct error ("asset failed verification — upstream changed or catalog is stale; try Refresh"). The verified sha256 is recorded in the install manifest.

**Version checks:** zero runtime Codeberg API calls. `latest_version` = the catalog's `derived_release`; `installed_version` comes from the install manifest. `refresh()` just re-fetches `mods.json` (update visibility lags the 6-hour workflow cadence at most). The QAM panel shows "Catalog updated: X ago" from the cached catalog's fetch timestamp.

**Extractor (hardened, new):**
- Normalize `\` → `/` in every zip entry name (SyberiaTWBFix's current release uses backslash separators, which stock `zipfile.extractall` turns into junk files on Linux).
- Zip-slip guard (applied after normalization, per entry): reject entries whose name is absolute, matches a drive-letter prefix (`^[A-Za-z]:`), or contains any `..` segment. Never create symlinks: skip entries whose `external_attr` upper bits mark `S_IFLNK`. Enforce containment on the **final** destination — after the case-insensitive remap — via `os.path.realpath(dest)` inside `os.path.realpath(target_dir)` (compare with trailing separator / `os.path.commonpath`); realpath resolution also prevents escape through pre-existing symlinked directories.
- Resource caps: reject archives declaring >10,000 entries or >4 GB total uncompressed; enforce the same limits on actual bytes written (zip headers can lie). Exceeding a cap aborts and triggers rollback.
- Skip the `EXTRACT_TO_GAME_FOLDER` marker file.
- **Target directory selection (no heuristics):** `zip_layout: pathed` → extract to the install root. `zip_layout: flat` with `install_subdir` on the game entry → extract to `install_path/install_subdir`. `zip_layout: flat` **without** `install_subdir` → the install is **blocked**: the row renders as `needs_curation` ("awaiting catalog data") and no Install button is shown. Silent wrong-place extraction (which would report "installed" while the fix never loads) is worse than refusing. The derivation warnings in Part 1 are the curation feed. (The earlier Unreal shipping-exe runtime heuristic is dropped: all known flat-layout mods get curated subdirs, and the heuristic couldn't cover the non-UE cases anyway.)
- Case-insensitive merge, bounded: a thin path-resolution walk that matches each path component against existing entries case-insensitively (prefer exact match, else the existing variant). If a component collides with an existing **file** where a directory is needed, or two existing entries differ only in case, fail the install with `extract_failed` — no general merge engine.
- Transactional rollback: every file overwritten during an install/update (including the mod's own previous-version files) is first copied to a per-operation staging dir; on failure, staged copies are restored and newly written files deleted; on success the staging dir is discarded.

**Pristine backups (distinct from rollback staging):** before overwriting a file, copy it to `DECKY_PLUGIN_RUNTIME_DIR/backups/<appid>-<mod_id>/<path relative to install root>` **only if it is pristine** — i.e. not listed in the current manifest's `files[]` for this (appid, mod_id). Backups are write-once; the mod's own files from a previous version are never backed up. (Review finding: the naive "back up before overwrite" rule would clobber pristine game files with mod v1 files on update, making uninstall restore the wrong bytes.)

**Install manifest:** `DECKY_PLUGIN_RUNTIME_DIR/installs/<appid>-<mod_id>.json` with `{schema: 1, mod_id, appid, version, sha256, install_path, target_dir, files[], backed_up_files[], wine_dll_override, launch_option_handled, installed_at}`. On update: carry `backed_up_files[]` forward unchanged, replace `files[]`/`version`/`sha256`, and delete files from the old `files[]` that the new release no longer ships. Uninstall: delete `files[]`, restore each `backed_up_files[]` entry to its recorded relative path, remove the manifest and backup dir. Status is re-derived from disk. `refresh()` prunes manifests (and backups) whose game install dir no longer exists — Steam removed the whole dir on game uninstall, so restoration is meaningless; a later game reinstall starts clean as `not_installed`.

**Concurrency & lifecycle (review finding):** one operation per appid at a time — an in-memory operations table `{appid: {op, mod_id, phase, pct}}`; `install()`/`uninstall()` validate, register the operation (returning `{ok: false, code: "already_in_progress"}` if the appid is busy), spawn the work as an asyncio task, and return `{ok: true, accepted: true}` immediately. Completion is delivered via `decky.emit("qf_done", mod_id, appid, ok, code?, wine_dll_override?)` — it must not depend on the frontend still awaiting the call. Progress via `decky.emit("qf_progress", mod_id, appid, phase, pct)` (pct from catalog `size` during download, entry-count during extraction; `null` = indeterminate). The running-game guard (scan `/proc` cmdlines for the install path) runs at operation start, **before** download.

**One mod per game:** if a manifest already exists for an appid, other catalog mods matching that appid render with Install disabled ("another fix is installed for this game") — two mods extracting into one game dir (e.g. two dsound proxies) would corrupt each other's state. Duplicate-appid rows themselves remain visible.

**DLO override status (best-effort probe):** read `<DECKY_USER_HOME>/.dlo/settings.json` (DLO's internal state file). Derive per-(mod, appid) `override_status`: `not_registered` if no `launchOptions[]` entry has id `lyall-<modId>`; else `registered_enabled` / `registered_disabled` from `profiles[appid].state`. Missing file, parse error, unexpected shape → `unknown`; the probe must never fail `get_state()`, and `unknown` renders neutrally (no false alarms). This file is DLO-internal, not a contract (verified at v1.12; the store build may differ) — hence best-effort only.

**Callables** (all return a structured envelope — see Error handling):
- `get_state()` → `{ok, catalog_updated_at, games: [{appid, mod_id, install_path, installed_version, latest_version, wine_dll_override, loader, status, override_status, busy}]}` where `status` ∈ `not_installed | installed | update_available | needs_curation | needs_launch_option | unknown` and `busy` = `{op, phase, pct} | null` from the operations table (so a remounted panel restores in-flight state without waiting for events).
- `refresh()` → re-fetch catalog, prune orphaned manifests.
- `install(mod_id, appid)` / `uninstall(mod_id, appid)` → `{ok, accepted}` or `{ok: false, code, message}`.

### Frontend (`src/`)

- `index.tsx`: `definePlugin`; `qf_progress`/`qf_done` listeners registered at module scope (removed in `onDismount`, not the panel component) so completion toasts and DLO registration fire even when the QAM panel is closed. `hasDeckyLaunchOptions` is read live on every render — never cached at mount (plugin load order is not guaranteed; DLO may load or be installed later).
- **QAM panel:** rows for detected games with catalog fixes — display name via `appStore.GetAppOverviewByAppID(appid)` (retry-wrapped), status line, context-aware button (Install / Update / Uninstall / disabled states), progress bar for `busy` rows, Refresh button with "Catalog updated: X ago". Rows sort by actionability: busy → update_available → installed-with-warning → installed → not_installed → needs_curation; stable order within groups so rows don't jump under controller focus.
- **Activation visibility (review finding — this is the plugin's primary failure mode):** an installed fix whose override isn't active loads nothing while the panel would happily say "Installed". When `status` is installed/update_available and `override_status` is `not_registered`/`registered_disabled`, the row shows a persistent warning ("Fix installed — launch override not enabled") plus a **"Register launch option"** button that re-dispatches the DLO event (safe: stable id upserts). This also covers the user declining/missing DLO's confirm dialog, which has no acknowledgment API.
- **DLO registration:** after a successful install (on `qf_done`), dispatch:
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
  Then a `showModal` ConfirmModal (not a transient toast) gives the activation path **matching DLO's real UI**: DLO's per-game toggles live on DLO's own per-app page, reached via the "Launch Options" item DLO splices into the game's context menu next to "Properties..." — the copy says: "Open the game's menu (the one with 'Properties...'), select 'Launch Options', and turn ON '<name>' under 'Lyall Fixes'." Do not deep-link DLO's route (unversioned internal). The BepInEx slow-first-boot warning is folded into this modal. Sequence it to not stack with DLO's own confirm modal (verify ordering on device). Uninstall shows the mirror instruction (turn OFF / remove).
- **Without DLO — degraded manual mode:** when `hasDeckyLaunchOptions` is falsy, a banner recommends installing "Launch Options" from the Decky store, but Install/Update/Uninstall stay enabled (the file-install work — subdir placement, backslash fixes — is value users can't easily replicate by hand). Post-install, a modal shows the exact line `WINEDLLOVERRIDES="<dll>=n,b" %command%` with copy-to-clipboard and instructions to paste it under the game's Properties → Launch Options (precedent: decky-16x10-fixes, Framegen manual mode). The install is marked `launch_option_handled: "manual_pending"` → `status: needs_launch_option` with a per-row "Copy launch option" affordance; cleared best-effort by a **read-only** check of `appDetailsStore.GetAppDetails(appid)?.strLaunchOptions` for the `WINEDLLOVERRIDES="<dll>=` token (no writes — the v1 lock on programmatic writes stands), or by an explicit "I've added it" confirmation. Manual options remain safe if DLO is installed later (DLO preserves and executes originals). *Note: this softens the original "hard-block without DLO" decision; flagged for user sign-off.*

### Error handling

Structured results are the only backend→frontend error contract: every callable catches internally and returns `{ok: false, code, message}` — never raises across the bridge. `code` is a small enum (`network_offline`, `verify_failed`, `no_asset`, `extract_failed`, `game_running`, `already_in_progress`, `needs_curation`, `unexpected`); `message` is a short human-written string sized for a toast (~60 chars), e.g. `game_running` → "Close the game before installing", `extract_failed` → "Install failed — game files restored". Full detail goes to `decky.logger` only. The frontend keeps a last-resort try/catch per invocation that toasts "Something went wrong — check the Decky log" and never displays raw exception text. Network failures fall back to the cached catalog.

### Plugin lifecycle

`_uninstall()` leaves installed fixes, manifests, and DLO options in place (removing mods from game dirs during plugin uninstall is surprising and unrecoverable); the README documents this, and Framegen sets the same expectation with an in-UI warning.

### Repo layout, CI, distribution

- Template-derived layout: `main.py`, `py_modules/lyall_core/` (detection, download, extract, manifest — unit-testable pure Python), `src/`, `plugin.json` (`flags: []`), `package.json`, `defaults/`.
- GitHub Actions: lint + pytest for `py_modules/lyall_core` (fixture zips: flat, pathed, backslash-entries, zip-slip via `..`, absolute-path entries, symlink entries — built programmatically with `ZipInfo.external_attr = 0o120777 << 16` — and over-limit bombs with lying size headers), `pnpm build`, decky CLI zip build; on tag push, attach the zip to a GitHub release.
- Install URL for users: `https://github.com/sharkusmanch/decky-lyall/releases/latest/download/decky-lyall.zip` via Decky Settings → Developer → Install from URL.
- Dev loop: rsync to `deck@<ip>:~/homebrew/plugins` + `systemctl restart plugin_loader`; CEF debugging via `chrome://inspect` → `<deck-ip>:8081`.

### Testing

- Unit tests (CI, no Deck): extractor rules against the fixture matrix above (incl. absolute-path/`..`/symlink rejection and resource caps); backup/update/uninstall round-trips (update must preserve pristine backups and remove no-longer-shipped files); manifest pruning; catalog validation rejects (bad mod_id, traversal `install_subdir`, off-host `download_url`, unknown override DLL); every error code returned without an exception escaping a callable.
- On-device smoke test (manual): one mod per shape — ClairObscurFix (flat + subdir + dsound), FF7RebirthFix (pathed + dsound), a winmm mod (e.g. MGSVFix), a BepInEx mod (e.g. RaidouFix) — verifying files land next to the shipping exe, sha256 verification passes, and the fix loads in-game with the toggle on. DLO choreography: dispatch with QAM open (modal visible/focusable), decline the import and confirm the row warns + "Register launch option" recovers, enable the toggle and confirm the warning clears; verify the instruction copy's menu labels against the DLO **store** build (which lags GitHub).

## Risks / notes

- `SteamClient`/`appStore` internals are unversioned Valve APIs; blast radius is display names and the read-only manual-mode check (worst case: appids shown, warning not auto-cleared).
- `~/.dlo/settings.json` is DLO-internal; the probe degrades to `unknown` and `unknown` never warns.
- DLO's store version lags GitHub; the integration event exists since v1.8 but field-level behavior is verified on-device against the store build.
- Steam game updates can break offset-based fixes until Lyall updates them — the update flow covers recovery; this is upstream of us.
- Catalog trust: pinned hashes protect against asset swaps and MITM; a compromised quickfix repo remains a trusted root (mitigated by the human-merged auto-refresh PR gate, verified present).

## Follow-ups (explicitly out of v1)

1. Use `install_subdir`/`zip_layout` in Windows `quickfix.py` (fixes the current Layout-B bug where the proxy DLL lands next to the launcher stub).
2. Upstream DLO feature request: programmatic per-app option enable/remove + an acknowledgment for `dlo-add-launch-options`.
3. Optional recipes.json for DLO's Recipes companion plugin as a code-free alternative channel.
4. INI config editor, per-game page integration, background update checks.
