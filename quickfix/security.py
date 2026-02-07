import hashlib
import os
import zipfile


def extract_zip_safe(zip_path, extract_to):
    """Extract a zip file while guarding against Zip Slip (path traversal).

    Returns a list of extracted relative paths (for file tracking).
    """
    extracted_files = []
    extract_to = os.path.realpath(extract_to)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            # Resolve the target path and ensure it stays within extract_to
            target_path = os.path.realpath(os.path.join(extract_to, member.filename))
            if not target_path.startswith(extract_to + os.sep) and target_path != extract_to:
                print(f"[WARN] Skipping potentially unsafe zip entry: {member.filename}")
                continue

            # Skip directories themselves; they are created implicitly
            if member.is_dir():
                os.makedirs(target_path, exist_ok=True)
                continue

            # Ensure parent directories exist
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with zf.open(member) as src, open(target_path, "wb") as dst:
                dst.write(src.read())

            # Store the relative path for file tracking
            extracted_files.append(member.filename)

    return extracted_files


def verify_download_integrity(zip_path, expected_hash=None):
    """Verify the SHA-256 hash of a downloaded file.

    If *expected_hash* is None this is a no-op (upstream does not yet
    provide checksum assets for all releases).
    """
    if expected_hash is None:
        return True

    sha256 = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)

    actual = sha256.hexdigest()
    if actual != expected_hash:
        print(f"[ERROR] Integrity check failed! Expected {expected_hash}, got {actual}")
        return False
    return True
