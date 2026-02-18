import os
import sys


def get_appdata_dir():
    """Return the QuickFix directory under %APPDATA%, creating it if needed.

    Exits with a clear error if APPDATA is not set.
    """
    appdata = os.getenv("APPDATA")
    if appdata is None:
        print("[ERROR] APPDATA environment variable is not set. Cannot determine config directory.")
        sys.exit(1)

    quickfix_dir = os.path.join(appdata, "QuickFix")
    os.makedirs(quickfix_dir, exist_ok=True)
    return quickfix_dir
