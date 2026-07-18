from derive_mod_metadata import analyze_zip


def test_flat_ual_zip():
    names = ["ClairObscurFix.asi", "ClairObscurFix.ini", "dsound.dll", "EXTRACT_TO_GAME_FOLDER"]
    meta = analyze_zip(names)
    assert meta == {"wine_dll_override": "dsound", "loader": "ual", "zip_layout": "flat"}


def test_pathed_ual_zip():
    names = ["End/Binaries/Win64/dsound.dll", "End/Binaries/Win64/FF7RebirthFix.asi",
             "End/Binaries/Win64/FF7RebirthFix.ini"]
    meta = analyze_zip(names)
    assert meta == {"wine_dll_override": "dsound", "loader": "ual", "zip_layout": "pathed"}


def test_backslash_entries_are_normalized():
    names = ["End\\Binaries\\Win64\\dsound.dll", "End\\Binaries\\Win64\\Fix.asi"]
    meta = analyze_zip(names)
    assert meta["wine_dll_override"] == "dsound"
    assert meta["zip_layout"] == "pathed"


def test_bepinex_zip_prefers_shallowest_proxy_dll():
    # dotnet runtime ships deep DLLs that shadow proxy names; depth breaks the tie
    names = ["winhttp.dll", "doorstop_config.ini", "BepInEx/core/BepInEx.dll",
             "dotnet/shared/version.dll"]
    meta = analyze_zip(names)
    assert meta == {"wine_dll_override": "winhttp", "loader": "bepinex", "zip_layout": "pathed"}


def test_melonloader_zip():
    names = ["version.dll", "MelonLoader/net6/MelonLoader.dll", "Mods/SyberiaTWBFix.dll"]
    meta = analyze_zip(names)
    assert meta["loader"] == "melonloader"
    assert meta["wine_dll_override"] == "version"


def test_no_known_proxy_dll_yields_none():
    names = ["Fix.asi", "dxgi.dll"]  # dxgi is deliberately excluded (DXVK conflict)
    assert analyze_zip(names)["wine_dll_override"] is None


def test_ambiguous_proxies_at_same_depth_yield_none():
    names = ["dsound.dll", "winmm.dll", "Fix.asi"]
    assert analyze_zip(names)["wine_dll_override"] is None

import hashlib
import io
import zipfile

from derive_mod_metadata import (
    collect_warnings,
    derive_mod,
    get_latest_zip_asset,
    needs_derivation,
    parse_release_assets,
)


def test_parse_release_assets_picks_zip_and_tag():
    data = {"tag_name": "v1.2.3", "assets": [
        {"name": "notes.txt", "browser_download_url": "https://x/notes.txt"},
        {"name": "Fix_v1.2.3.zip", "browser_download_url": "https://x/Fix.zip"},
    ]}
    assert parse_release_assets(data) == {"tag": "v1.2.3", "url": "https://x/Fix.zip"}


def test_parse_release_assets_prefers_non_xbox_zip():
    # GitHub releases often ship a Steam zip and an _Xbox variant; the Steam
    # build is the one QuickFix installs.
    data = {"tag_name": "v0.0.9", "assets": [
        {"name": "STALKER2Tweak_v0.0.9_Xbox.zip", "browser_download_url": "https://x/xbox.zip"},
        {"name": "STALKER2Tweak_v0.0.9.zip", "browser_download_url": "https://x/steam.zip"},
    ]}
    assert parse_release_assets(data)["url"] == "https://x/steam.zip"


def test_parse_release_assets_none_without_zip():
    assert parse_release_assets({"tag_name": "v1", "assets": [
        {"name": "readme.md", "browser_download_url": "https://x/readme.md"}]}) is None


def test_get_latest_zip_asset_falls_back_to_github(monkeypatch):
    import derive_mod_metadata as d

    class Resp:
        def __init__(self, status, data=None):
            self.status_code = status
            self._data = data or {}

        def json(self):
            return self._data

    gh_payload = {"tag_name": "v0.0.9", "assets": [
        {"name": "Fix_v0.0.9.zip", "browser_download_url": "https://github.com/Lyall/Fix.zip"}]}
    monkeypatch.setattr(d, "codeberg_get", lambda url: Resp(404))
    monkeypatch.setattr(d, "github_get", lambda url: Resp(200, gh_payload))

    assert get_latest_zip_asset("Lyall/Fix") == {
        "tag": "v0.0.9", "url": "https://github.com/Lyall/Fix.zip"}


def test_get_latest_zip_asset_prefers_codeberg(monkeypatch):
    import derive_mod_metadata as d

    class Resp:
        def __init__(self, status, data=None):
            self.status_code = status
            self._data = data or {}

        def json(self):
            return self._data

    cb_payload = {"tag_name": "1.0", "assets": [
        {"name": "Fix.zip", "browser_download_url": "https://codeberg.org/Lyall/Fix.zip"}]}
    calls = {"github": 0}

    def gh(url):
        calls["github"] += 1
        return Resp(404)

    monkeypatch.setattr(d, "codeberg_get", lambda url: Resp(200, cb_payload))
    monkeypatch.setattr(d, "github_get", gh)

    assert get_latest_zip_asset("Lyall/Fix")["url"] == "https://codeberg.org/Lyall/Fix.zip"
    assert calls["github"] == 0  # codeberg hit means no github call


def _zip_blob(names):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for n in names:
            zf.writestr(n, b"x")
    return buf.getvalue()


def test_needs_derivation_on_new_tag_or_missing_fields():
    mod = {"derived_release": "0.0.1", "wine_dll_override": "dsound", "loader": "ual",
           "zip_layout": "flat", "download_url": "u", "sha256": "s", "size": 1}
    assert not needs_derivation(mod, "0.0.1")
    assert needs_derivation(mod, "0.0.2")
    del mod["sha256"]
    assert needs_derivation(mod, "0.0.1")


def test_derive_mod_sets_all_fields():
    blob = _zip_blob(["Fix.asi", "dsound.dll", "Fix.ini"])
    mod = {"repo": "Lyall/Fix", "games": [{"steam_appid": 1}]}
    derive_mod(mod, {"tag": "0.0.5", "url": "https://codeberg.org/x/Fix.zip"}, blob)
    assert mod["wine_dll_override"] == "dsound"
    assert mod["zip_layout"] == "flat"
    assert mod["derived_release"] == "0.0.5"
    assert mod["download_url"] == "https://codeberg.org/x/Fix.zip"
    assert mod["sha256"] == hashlib.sha256(blob).hexdigest()
    assert mod["size"] == len(blob)


def test_derive_mod_keeps_old_override_when_underivable():
    blob = _zip_blob(["Fix.asi"])  # no proxy DLL found
    mod = {"repo": "Lyall/Fix", "wine_dll_override": "winmm", "games": []}
    derive_mod(mod, {"tag": "0.0.6", "url": "u"}, blob)
    assert mod["wine_dll_override"] == "winmm"  # not clobbered with None


def test_collect_warnings():
    mods = {
        "NoOverride": {"games": [{"steam_appid": 1}], "zip_layout": "pathed"},
        "FlatNoSubdir": {"wine_dll_override": "dsound", "zip_layout": "flat",
                          "games": [{"steam_appid": 2}]},
        "Empty": {"wine_dll_override": "dsound", "zip_layout": "pathed", "games": []},
        "DupA": {"wine_dll_override": "dsound", "zip_layout": "pathed",
                 "games": [{"steam_appid": 3}]},
        "DupB": {"wine_dll_override": "dsound", "zip_layout": "pathed",
                 "games": [{"steam_appid": 3}]},
    }
    warnings = collect_warnings(mods)
    text = "\n".join(warnings)
    assert "NoOverride" in text and "wine_dll_override" in text
    assert "FlatNoSubdir" in text and "install_subdir" in text
    assert "Empty" in text and "games" in text
    assert "DupA" in text and "DupB" in text
