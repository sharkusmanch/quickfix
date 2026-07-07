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
