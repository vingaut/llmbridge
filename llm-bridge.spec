# -*- mode: python ; coding: utf-8 -*-
# Spec PyInstaller — un seul exécutable, interface web embarquée.
#   pyinstaller --clean --noconfirm llm-bridge.spec
# Le même fichier produit dist/LLMBridge.exe sous Windows et dist/LLMBridge sous Linux.

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('web/index.html', 'web'),        # interface embarquée
        ('assets/cacert.pem', 'assets'),  # racines TLS (https hors magasin système)
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # rien de tout cela n'est importé par app.py : on allège l'exécutable
        'tkinter', '_tkinter', 'unittest', 'pydoc', 'doctest', 'pdb',
        'sqlite3', 'setuptools', 'pip', 'wheel', 'pkg_resources',
        'multiprocessing', 'lib2to3', 'distutils', 'test',
    ],
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
    name='LLMBridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,              # passer à False pour un exe sans fenêtre noire
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/llmbridge.ico',   # décommenter après avoir déposé une icône
)
