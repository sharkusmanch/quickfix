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

from derive_mod_metadata import collect_warnings, derive_mod, needs_derivation


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
