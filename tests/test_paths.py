import os
from unittest import mock

import pytest

from quickfix.paths import get_appdata_dir


def test_appdata_none_exits():
    """Missing APPDATA env var causes sys.exit."""
    with mock.patch.dict(os.environ, {}, clear=True):
        # Ensure APPDATA is truly missing
        env = os.environ.copy()
        env.pop("APPDATA", None)
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                get_appdata_dir()
            assert exc_info.value.code == 1


def test_appdata_returns_dir(tmp_path):
    """When APPDATA is set, returns QuickFix subdirectory."""
    with mock.patch.dict(os.environ, {"APPDATA": str(tmp_path)}):
        result = get_appdata_dir()
        assert result == os.path.join(str(tmp_path), "QuickFix")
        assert os.path.isdir(result)
