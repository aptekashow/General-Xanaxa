# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [("assets", "assets")]
binaries = []
hiddenimports = [
    "qwen_tts", "torch", "torchaudio", "torchvision",
    "transformers", "tokenizers", "soundfile", "lameenc",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
]
for package in ["qwen_tts", "torch", "torchaudio", "torchvision", "transformers", "tokenizers", "soundfile", "lameenc"]:
    try:
        d, b, h = collect_all(package)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "notebook", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="GeneralXanaxa",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/icon.ico",
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name="GeneralXanaxa",
)
