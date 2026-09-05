# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['revised_d2r_mf_tracker_v10.py'],
    pathex=[],
    binaries=[],
    datas=[],
    # The screen-reading deps are imported inside try/except blocks, so name
    # them explicitly rather than relying on PyInstaller's static analysis.
    hiddenimports=[
        'd2r_vision',
        'd2r_autodetect',
        'mss',
        'numpy',
        'PIL',
        'pytesseract',
        'rapidfuzz',
        'keyboard',
    ],
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
    a.binaries,
    a.datas,
    [],
    name='revised_d2r_mf_tracker_v10',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
