
# QuickFix

QuickFix is a CLI tool to easily install, update, and manage Lyall's PC game fixes from GitHub.

## 🚀 Features

- Install and update mods automatically from GitHub releases
- Automatically detect installed Steam games
- Merge config files intelligently to preserve user settings
- Semantic versioning and clean GitHub releases
- Manage config files easily
- Debug logging for troubleshooting
- Custom Steam directories support

## 📦 Installation

1. Download the latest release from the [Releases](https://github.com/sharkusmanch/quickfix/releases) page.
2. Run `quickfix.exe` or `python quickfix.py` if using the source.

## 🧩 Commands

### Install a mod

```bash
python quickfix.py install <mod_id>
```

Example:

```bash
python quickfix.py install ClairObscurFix
```

### Install all available mods

```bash
python quickfix.py install --all
```

This will install all mods for detected installed games that don't already have the latest version installed.

### Update all mods

```bash
python quickfix.py update --all
```

Force re-download and update all installed mods.

### 📂 Open a mod's config file

```bash
python quickfix.py open-config <mod_id>
```

Example:

```bash
python quickfix.py open-config ClairObscurFix
```

QuickFix will find and open the config file inside the installed game's directory.

### 🐛 Enable debug logging

Add `--debug` to any command:

```bash
python quickfix.py install ClairObscurFix --debug
```

Shows detailed Steam scanning, GitHub API requests, and file operations.

### 📂 Use custom Steam directories

Specify one or multiple custom Steam game libraries:

```bash
python quickfix.py install ClairObscurFix --steam-dir "D:\SteamLibrary"
```

Or multiple:

```bash
python quickfix.py install ClairObscurFix --steam-dir "D:\SteamLibrary" --steam-dir "E:\Games\SteamLibrary"
```

## ⚙️ Advanced Usage

- Open a mod's config file: `python quickfix.py open-config <mod_id>`
- Enable debug logging: `python quickfix.py --debug install <mod_id>`
- Set custom Steam game directories: `python quickfix.py --steam-dir "<path>" install <mod_id>`

## 🛡 Security Disclaimer

**Use at your own risk!**  
QuickFix downloads and installs files from third-party GitHub repositories (Lyall).  
Always exercise caution when running scripts or modifying your game installations.

## 🛠 Development

Install requirements:

```bash
pip install pyinstaller requests
```

Build executable:

```bash
pyinstaller --onefile quickfix.py
```

## 📜 License

MIT License (see LICENSE file).

---

Made with ❤️ for PC gamers by [sharkusmanch](https://github.com/sharkusmanch).
