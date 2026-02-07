import os
import tempfile
import zipfile

from quickfix.security import extract_zip_safe


def test_zip_slip_blocked(tmp_path):
    """Malicious zip entry with ../ is skipped."""
    zip_path = os.path.join(str(tmp_path), "evil.zip")
    extract_to = os.path.join(str(tmp_path), "output")
    os.makedirs(extract_to)

    with zipfile.ZipFile(zip_path, "w") as zf:
        # Normal file
        zf.writestr("safe.txt", "hello")
        # Malicious path traversal entry
        zf.writestr("../../etc/evil.txt", "pwned")

    extracted = extract_zip_safe(zip_path, extract_to)

    # Only the safe file should be extracted
    assert "safe.txt" in extracted
    assert any("evil" in f for f in extracted) is False
    assert os.path.isfile(os.path.join(extract_to, "safe.txt"))
    assert not os.path.exists(os.path.join(extract_to, "..", "..", "etc", "evil.txt"))


def test_normal_extraction(tmp_path):
    """Regular zip extracts correctly and returns file list."""
    zip_path = os.path.join(str(tmp_path), "good.zip")
    extract_to = os.path.join(str(tmp_path), "output")
    os.makedirs(extract_to)

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("mod.dll", b"\x00" * 10)
        zf.writestr("subdir/config.ini", "[settings]\nkey=value")

    extracted = extract_zip_safe(zip_path, extract_to)

    assert "mod.dll" in extracted
    assert "subdir/config.ini" in extracted
    assert os.path.isfile(os.path.join(extract_to, "mod.dll"))
    assert os.path.isfile(os.path.join(extract_to, "subdir", "config.ini"))
