# -*- mode: python ; coding: utf-8 -*-


from PyInstaller.utils.hooks import collect_data_files

# Incluye los modelos ONNX de detección de voz que necesita faster-whisper.
whisper_data = collect_data_files("faster_whisper")
if not any(source.lower().endswith(".onnx") for source, _ in whisper_data):
    raise RuntimeError(
        "No se encontraron los modelos ONNX de faster-whisper. "
        "Instala faster-whisper en el entorno de compilación antes de continuar."
    )

a = Analysis(
    ['app\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('app', 'app'), ('ico.png', '.')] + whisper_data,
    hiddenimports=[],
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
    name='YouTubeDownloader',
    icon='ico.ico',
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
    name='YouTubeDownloader',
)
