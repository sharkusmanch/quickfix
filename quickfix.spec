# quickfix.spec

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['quickfix.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['requests'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

# Build the executable as one file
exe = EXE(
    a,
    Tree('data'),
    exclude_binaries=False,
    name='quickfix',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
