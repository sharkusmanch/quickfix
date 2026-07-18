from validate_mods import validate_entry, collect_cross_mod_warnings, repo_exists


class _Resp:
    def __init__(self, status):
        self.status_code = status


def test_repo_exists_true_when_on_codeberg(monkeypatch):
    import validate_mods as v
    monkeypatch.setattr(v, "codeberg_get", lambda url: _Resp(200))
    monkeypatch.setattr(v, "github_get", lambda url: _Resp(404))
    assert repo_exists("Lyall/FooFix") is True


def test_repo_exists_true_when_only_on_github(monkeypatch):
    import validate_mods as v
    monkeypatch.setattr(v, "codeberg_get", lambda url: _Resp(404))
    monkeypatch.setattr(v, "github_get", lambda url: _Resp(200))
    assert repo_exists("Lyall/FooFix") is True


def test_repo_exists_false_when_nowhere(monkeypatch):
    import validate_mods as v
    monkeypatch.setattr(v, "codeberg_get", lambda url: _Resp(404))
    monkeypatch.setattr(v, "github_get", lambda url: _Resp(404))
    assert repo_exists("Lyall/GhostFix") is False


def _valid():
    return {
        "repo": "Lyall/FooFix",
        "config_files": ["FooFix.ini"],
        "games": [{"steam_appid": 42, "install_subdir": "Foo/Binaries/Win64"}],
        "wine_dll_override": "dsound",
        "loader": "ual",
        "zip_layout": "flat",
        "derived_release": "0.0.1",
        "download_url": "https://codeberg.org/Lyall/FooFix/releases/download/0.0.1/F.zip",
        "sha256": "0" * 64,
        "size": 100,
    }


def test_valid_entry_has_no_errors():
    assert validate_entry("FooFix", _valid()) == []


def test_unknown_override_rejected():
    mod = _valid()
    mod["wine_dll_override"] = "dxgi"
    assert any("wine_dll_override" in e for e in validate_entry("FooFix", mod))


def test_unsafe_install_subdir_rejected():
    for bad in ("/abs/path", "a/../../b", ".."):
        mod = _valid()
        mod["games"][0]["install_subdir"] = bad
        assert any("install_subdir" in e for e in validate_entry("FooFix", mod)), bad


def test_bad_sha256_rejected_when_derived():
    mod = _valid()
    mod["sha256"] = "not-a-hash"
    assert any("sha256" in e for e in validate_entry("FooFix", mod))


def test_offsite_download_url_rejected():
    mod = _valid()
    mod["download_url"] = "https://evil.example.com/F.zip"
    assert any("download_url" in e for e in validate_entry("FooFix", mod))


def test_github_download_url_accepted():
    # GitHub-hosted fixes (not mirrored to Codeberg) derive github.com asset URLs.
    mod = _valid()
    mod["download_url"] = "https://github.com/Lyall/FooFix/releases/download/0.0.1/F.zip"
    assert not any("download_url" in e for e in validate_entry("FooFix", mod))


def test_underived_entry_needs_no_pinning_fields():
    mod = {"repo": "Lyall/New", "config_files": ["New.ini"], "games": [{"steam_appid": 7}]}
    assert validate_entry("New", mod) == []


def test_empty_games_is_warning_not_error():
    mod = {"repo": "Lyall/New", "config_files": ["New.ini"], "games": []}
    assert validate_entry("New", mod) == []
    warnings = collect_cross_mod_warnings({"New": mod})
    assert any("games" in w for w in warnings)


def test_duplicate_appid_warning():
    mods = {"A": _valid(), "B": _valid()}
    warnings = collect_cross_mod_warnings(mods)
    assert any("42" in w for w in warnings)
