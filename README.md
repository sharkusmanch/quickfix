# QuickFix

**QuickFix** is a lightweight, CLI-based tool to manage, install, and update community-made PC game fixes and tweaks.

Originally built for managing [Lyall](https://github.com/Lyall)'s fixes, QuickFix is designed to be general-purpose, dynamic, and safe — fetching only the latest approved patches directly from GitHub.

---

## ✨ Features

- ✅ Auto-detects installed Steam games
- ✅ Fetches latest fixes dynamically from GitHub
- ✅ Caches mod list locally for faster performance (1 hour expiry)
- ✅ Force-refresh mods list manually if needed
- ✅ Merges user-edited `.ini` configs intelligently during updates
- ✅ Supports custom mods list override with `--mods`
- ✅ Fully portable: available as standalone `.exe` or simple Python script

---

## 📦 Usage

You can either:

- Run directly with **Python** (`python quickfix.py`)
or
- Use the **self-contained executable** (`quickfix.exe`)

---

## 🚀 Commands

| Command | Description |
|:---|:---|
| `install <mod_id>` | Install a specific fix (skips if already installed) |
| `install --all` | Install all available fixes for detected games |
| `update <mod_id>` | Update a specific fix if outdated |
| `update --all` | Update all installed fixes |
| `list` | Show all available fixes |
| `installed` | Show installed fixes and their versions |

---

## ⚙️ Options

| Option | Description |
|:---|:---|
| `--mods <path>` | Use a custom `mods.json` instead of fetching from GitHub |
| `--force-refresh` | Force downloading the latest `mods.json` even if cache is still fresh |

---

## 🛡 Security Disclaimer

> **Warning:**
> QuickFix downloads and installs community-made patches directly into your local game directories.
>
> While every effort is made to support reputable sources (like [Lyall](https://github.com/Lyall)), you should **always exercise caution** when installing third-party content into your system.
>
> Only use trusted mods, review GitHub releases when possible, and never run QuickFix (or any mod manager) with elevated/admin privileges unless absolutely necessary.

---

## 📚 How It Works

1. **QuickFix fetches `mods.json`** dynamically from the GitHub repository.
2. **Mods list is cached** locally for 1 hour (`.cache/mods.json`) to minimize API calls.
3. **Smart version checking** avoids unnecessary reinstalls.
4. **Custom config merging** preserves your `.ini` tweaks when updating mods.
5. **User can override** mods source via `--mods` or force an update with `--force-refresh`.

---

## 🛠 Development

To build your own executable:

1. Install [PyInstaller](https://pyinstaller.org/):

   ```bash
   pip install pyinstaller
   ```

2. Build:
    ```bash
    pyinstaller --onefile --add-data "mods.json:." --name quickfix quickfix.py
    ```

    Output will be in the dist/ folder.

## 📍 License

This project is licensed under the MIT License.

## 📬 Credits

- Built originally for [Lyall](https://github.com/Lyall)'s PC game fixes
- Inspired by the need for a safer, centralized way to manage essential patches

---
