
# QuickFix

QuickFix is a CLI tool to easily install, update, uninstall, and manage Lyall's PC game fixes.

## Features

- Install, update, and uninstall mods automatically from Codeberg releases
- Automatically detect installed Steam games via the Windows registry
- Local cache for mods list (6-hour TTL) to reduce network requests
- Manage config files easily
- Debug logging for troubleshooting

## Installation

1. Download the latest release from the [Releases](https://github.com/sharkusmanch/quickfix/releases) page.
2. Run `quickfix.exe` or `python quickfix.py` if using the source.

## Commands

### Install a mod

```bash
quickfix install <mod_id>
```

Example:

```bash
quickfix install ClairObscurFix
```

### Install all available mods

```bash
quickfix install --all
```

This will install all mods for detected installed games that don't already have the latest version installed.

### Update a specific mod

```bash
quickfix update <mod_id>
```

### Update all mods

```bash
quickfix update --all
```

### Uninstall a mod

```bash
quickfix uninstall <mod_id>
```

Removes tracked files from the game directory and cleans up the installed.json entry. Mods installed before file tracking was added will have their entry removed but files must be cleaned up manually.

### List all available mods

```bash
quickfix list-mods
```

### List installed mods

```bash
quickfix list-installed
```

Shows all installed mods, their versions, and whether they can be cleanly uninstalled.

### Update the local mods cache

```bash
quickfix update-cache
```

Forces a fresh download of the mods list, bypassing the 6-hour cache.

### Open a mod's config file

```bash
quickfix open-config <mod_id>
```

QuickFix will find and open the config file inside the installed game's directory.

### Enable debug logging

Add `--debug` to any command:

```bash
quickfix install ClairObscurFix --debug
```

Shows detailed Steam scanning, API requests, and file operations.

## Development

Install requirements:

```bash
pip install -r requirements-dev.txt
```

Run tests:

```bash
python -m pytest tests/ -v
```

Build executable:

```bash
pyinstaller quickfix.spec
```

## Security Disclaimer

**Use at your own risk!**
QuickFix downloads and installs files from third-party Codeberg repositories (Lyall).
Always exercise caution when running scripts or modifying your game installations.

## License

MIT License (see LICENSE file).

---

Made with love for PC gamers by [sharkusmanch](https://github.com/sharkusmanch).
