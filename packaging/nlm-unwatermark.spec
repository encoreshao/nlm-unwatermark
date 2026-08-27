# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for nlm-unwatermark
#
# Run from the repo root: python -m PyInstaller packaging/nlm-unwatermark.spec --noconfirm

import os

block_cipher = None
project_root = os.path.dirname(SPECPATH)

a = Analysis(
    [os.path.join(SPECPATH, 'entry_point.py')],
    pathex=[project_root],
    binaries=[],
    datas=[],
    hiddenimports=[
        'fitz',
        'cv2',
        'numpy',
        'PIL',
        'PIL.Image',
        'tqdm',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='nlm-unwatermark',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
