import argparse

import quickfix
from quickfix import __version__
from quickfix.cache import get_mods
from quickfix.mods import (
    install_mod,
    install_all_mods,
    update_mod,
    update_all_mods,
    uninstall_mod,
    list_installed_mods,
    open_config_files,
)


def main():
    parser = argparse.ArgumentParser(description="QuickFix - Manage Lyall's PC Game Fixes")
    parser.add_argument(
        "command",
        choices=[
            "install",
            "update",
            "uninstall",
            "update-cache",
            "open-config",
            "list-mods",
            "list-installed",
        ],
        help="Command to run",
    )
    parser.add_argument("mod_id", nargs="?", help="Mod ID (for install, update, uninstall, open-config)")
    parser.add_argument("--all", action="store_true", help="Install or update all mods")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--version", action="version", version=__version__, help="Show the version")

    args = parser.parse_args()

    if args.debug:
        quickfix.DEBUG_MODE = True

    # Commands that need NO network / mods.json
    if args.command == "list-installed":
        list_installed_mods()
        return

    if args.command == "uninstall":
        if args.mod_id:
            uninstall_mod(args.mod_id)
        else:
            print("[ERROR] Please specify a mod ID to uninstall.")
        return

    # Commands that use mods.json (cache-first)
    if args.command == "update-cache":
        mods = get_mods(force_remote=True)
        print("[INFO] Cache updated successfully.")
        return

    mods = get_mods()

    if args.command == "install":
        if args.all:
            install_all_mods(mods)
        elif args.mod_id:
            install_mod(args.mod_id, mods)
        else:
            print("[ERROR] Please specify a mod ID or --all")
    elif args.command == "update":
        if args.all:
            update_all_mods(mods)
        elif args.mod_id:
            update_mod(args.mod_id, mods)
        else:
            print("[ERROR] Please specify a mod ID or --all")
    elif args.command == "open-config":
        if args.mod_id:
            open_config_files(args.mod_id, mods)
        else:
            print("[ERROR] Please specify a mod ID to open its config files.")
    elif args.command == "list-mods":
        print("[INFO] Listing all available mods:")
        for mod_id in mods.keys():
            print(f"- {mod_id}")
