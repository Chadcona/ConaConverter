# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for ConaConverter
#
# Build commands:
#   Windows:  pyinstaller ConaConverter.spec
#   macOS:    pyinstaller ConaConverter.spec
#   Linux:    pyinstaller ConaConverter.spec  (then wrap in AppImage)
#
# Generates a dist/ConaConverter/ folder. Distribute as a zip (Windows/Linux)
# or .app bundle (macOS).

from PyInstaller.utils.hooks import collect_data_files, collect_all

block_cipher = None

# Collect data files from DJ parsing libraries
datas = []
try:
    datas += collect_data_files("pyrekordbox")
except Exception:
    pass
try:
    datas += collect_data_files("serato_tools")
except Exception:
    pass

a = Analysis(
    ["conaconverter/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtWidgets",
        "PySide6.QtGui",
        "pyrekordbox",
        "pyrekordbox.rbxml",
        "serato_tools",
        "serato_tools.crate",
        "serato_tools.track",
        "mutagen",
        "mutagen.mp3",
        "mutagen.flac",
        "mutagen.mp4",
        "zlib",
        "sqlite3",
    ],
    hookspath=[],
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
    [],
    exclude_binaries=True,
    name="ConaConverter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",  # Uncomment and add icon file when ready
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ConaConverter",
)

# macOS .app bundle — uncomment when building on macOS
# app = BUNDLE(
#     coll,
#     name="ConaConverter.app",
#     icon="assets/icon.icns",
#     bundle_identifier="com.conaconverter.app",
#     info_plist={
#         "CFBundleDisplayName": "ConaConverter",
#         "CFBundleShortVersionString": "1.0.0",
#         "NSHighResolutionCapable": True,
#     },
# )
