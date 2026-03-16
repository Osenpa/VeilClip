# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path.cwd()
version_file = project_root / "packaging" / "version_info.txt"
hiddenimports = [
    "Crypto.Cipher.AES",
    "Crypto.Util.Padding",
    "win32timezone",
    "win32com.client",
    "pythoncom",
]

datas = [
    (str(project_root / "assets"), "assets"),
    (str(project_root / "locales"), "locales"),
]


a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VeilClip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(project_root / "assets" / "icon.ico"),
    version=str(version_file),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VeilClip",
)
