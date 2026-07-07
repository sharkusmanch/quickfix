from update_mods import refresh_existing_entry


def _entry():
    return {
        "repo": "Lyall/FooFix",
        "config_files": ["FooFix.ini"],
        "games": [{"steam_appid": 1, "install_subdir": "Foo/Binaries/Win64"}],
        "last_updated": "old",
        "wine_dll_override": "dsound",
        "loader": "ual",
        "zip_layout": "flat",
        "derived_release": "0.0.1",
        "download_url": "https://codeberg.org/Lyall/FooFix/releases/download/0.0.1/FooFix_0.0.1.zip",
        "sha256": "a" * 64,
        "size": 123,
    }


def test_refresh_preserves_derived_fields():
    existing = _entry()
    out = refresh_existing_entry(existing, "Lyall/FooFix", "new-timestamp")
    assert out["last_updated"] == "new-timestamp"
    assert out["wine_dll_override"] == "dsound"
    assert out["sha256"] == "a" * 64
    assert out["games"][0]["install_subdir"] == "Foo/Binaries/Win64"


def test_refresh_does_not_mutate_input():
    existing = _entry()
    refresh_existing_entry(existing, "Lyall/FooFix", "new-timestamp")
    assert existing["last_updated"] == "old"


def test_refresh_unchanged_when_timestamp_same():
    existing = _entry()
    out = refresh_existing_entry(existing, "Lyall/FooFix", "old")
    assert out == existing
