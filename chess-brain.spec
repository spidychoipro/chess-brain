# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['googleapiclient', 'googleapiclient.discovery', 'googleapiclient.http', 'google_auth_oauthlib', 'google_auth_oauthlib.flow', 'google.auth', 'google.auth.transport', 'google.auth.transport.requests'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'lib2to3', 'test', 'curses', 'turtledemo', 'turtle', 'idlelib', 'pydoc', 'pydoc_data', 'doctest', 'ensurepip', 'venv', 'xmlrpc', '__main__'],
    noarchive=False,
    optimize=0,
)
# Qt on this Windows build uses the OS ICU API. A MinGW/rclone ICU with
# version-suffixed exports can be picked up from PATH and break QtCore import.
a.binaries = [entry for entry in a.binaries
              if entry[0].replace('\\', '/').rsplit('/', 1)[-1].lower()
              not in {'icuuc.dll', 'icudt78.dll'}]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='chess-brain',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='chess-brain',
)

