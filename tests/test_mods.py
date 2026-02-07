import json
import os
from unittest import mock

from quickfix.mods import load_installed_mods, save_installed_mods, uninstall_mod


def _make_installed_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


def test_legacy_format_migration(tmp_path):
    """Old {"Mod": "v1.0"} format auto-migrates to new dict format."""
    qf_dir = os.path.join(str(tmp_path), "QuickFix")
    installed_path = os.path.join(qf_dir, "installed.json")
    _make_installed_json(installed_path, {"TestMod": "v1.0.0"})

    with mock.patch("quickfix.mods.get_appdata_dir", return_value=qf_dir):
        result = load_installed_mods()

    assert isinstance(result["TestMod"], dict)
    assert result["TestMod"]["version"] == "v1.0.0"
    assert result["TestMod"]["files"] == []
    assert result["TestMod"]["game_appid"] is None

    # Verify the file was updated on disk
    with open(installed_path) as f:
        on_disk = json.load(f)
    assert isinstance(on_disk["TestMod"], dict)


def test_uninstall_tracked_files(tmp_path):
    """Files are deleted and mod is removed from installed.json."""
    qf_dir = os.path.join(str(tmp_path), "QuickFix")
    game_dir = os.path.join(str(tmp_path), "game")
    os.makedirs(game_dir, exist_ok=True)

    # Create the file that the mod "installed"
    mod_file = os.path.join(game_dir, "mod.dll")
    with open(mod_file, "w") as f:
        f.write("fake dll")

    installed_data = {
        "TestMod": {
            "version": "v1.0.0",
            "files": ["mod.dll"],
            "game_appid": 12345,
        }
    }
    installed_path = os.path.join(qf_dir, "installed.json")
    _make_installed_json(installed_path, installed_data)

    with mock.patch("quickfix.mods.get_appdata_dir", return_value=qf_dir), \
         mock.patch("quickfix.mods.find_steam_game_install_path", return_value=game_dir):
        uninstall_mod("TestMod")

    # File should be gone
    assert not os.path.exists(mod_file)

    # installed.json should no longer have TestMod
    with open(installed_path) as f:
        data = json.load(f)
    assert "TestMod" not in data


def test_uninstall_untracked_warns(tmp_path, capsys):
    """Pre-tracking mod warns and removes entry only."""
    qf_dir = os.path.join(str(tmp_path), "QuickFix")

    installed_data = {
        "OldMod": {
            "version": "v0.5.0",
            "files": [],
            "game_appid": None,
        }
    }
    installed_path = os.path.join(qf_dir, "installed.json")
    _make_installed_json(installed_path, installed_data)

    with mock.patch("quickfix.mods.get_appdata_dir", return_value=qf_dir):
        uninstall_mod("OldMod")

    captured = capsys.readouterr()
    assert "before file tracking" in captured.out

    with open(installed_path) as f:
        data = json.load(f)
    assert "OldMod" not in data
