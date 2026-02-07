import json
import os
import time
from unittest import mock

from quickfix.cache import get_mods, CACHE_TTL_HOURS, _MODS_CACHE_FILE, _CACHE_META_FILE


def _write_cache_files(appdata_dir, mods_data, fetched_at):
    """Helper to write cache files for testing."""
    qf_dir = os.path.join(appdata_dir, "QuickFix")
    os.makedirs(qf_dir, exist_ok=True)

    with open(os.path.join(qf_dir, _MODS_CACHE_FILE), "w") as f:
        json.dump(mods_data, f)

    with open(os.path.join(qf_dir, _CACHE_META_FILE), "w") as f:
        json.dump({"fetched_at": fetched_at}, f)


FAKE_MODS = {"TestMod": {"repo": "Lyall/TestMod", "config_files": ["Test.ini"], "games": []}}
REMOTE_MODS = {"RemoteMod": {"repo": "Lyall/RemoteMod", "config_files": ["R.ini"], "games": []}}


def test_cache_valid_when_fresh(tmp_path):
    """Cache < 6h old is used (no remote fetch)."""
    appdata_dir = str(tmp_path)
    _write_cache_files(appdata_dir, FAKE_MODS, time.time() - 60)  # 1 minute ago

    with mock.patch("quickfix.cache.get_appdata_dir", return_value=os.path.join(appdata_dir, "QuickFix")), \
         mock.patch("quickfix.cache.fetch_latest_mods_json") as mock_fetch:
        result = get_mods()

    mock_fetch.assert_not_called()
    assert "TestMod" in result


def test_cache_invalid_when_expired(tmp_path):
    """Cache > 6h old triggers remote fetch."""
    appdata_dir = str(tmp_path)
    expired_time = time.time() - (CACHE_TTL_HOURS * 3600 + 1)
    _write_cache_files(appdata_dir, FAKE_MODS, expired_time)

    with mock.patch("quickfix.cache.get_appdata_dir", return_value=os.path.join(appdata_dir, "QuickFix")), \
         mock.patch("quickfix.cache.fetch_latest_mods_json", return_value=REMOTE_MODS) as mock_fetch:
        result = get_mods()

    mock_fetch.assert_called_once()
    assert "RemoteMod" in result


def test_cache_invalid_when_missing(tmp_path):
    """No cache files triggers remote fetch."""
    qf_dir = os.path.join(str(tmp_path), "QuickFix")
    os.makedirs(qf_dir, exist_ok=True)

    with mock.patch("quickfix.cache.get_appdata_dir", return_value=qf_dir), \
         mock.patch("quickfix.cache.fetch_latest_mods_json", return_value=REMOTE_MODS) as mock_fetch:
        result = get_mods()

    mock_fetch.assert_called_once()
    assert "RemoteMod" in result
