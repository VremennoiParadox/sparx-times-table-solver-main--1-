# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — builds Sparx Solver Pro.app on macOS."""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

spec_dir = Path(SPECPATH)
project_root = spec_dir.parent

block_cipher = None

# EasyOCR models staged by scripts/download_models.py
models_src = project_root / "bundle" / "models" / "easyocr"
datas = []
if models_src.is_dir() and any(models_src.iterdir()):
    datas.append((str(models_src), "models/easyocr"))
else:
    print(
        "WARNING: No staged EasyOCR models at bundle/models/easyocr.\n"
        "         Run: python scripts/download_models.py"
    )

hiddenimports = [
    "PIL._tkinter_finder",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "customtkinter",
    "easyocr",
    "torch",
    "cv2",
    "sympy",
    "pyautogui",
    "numpy",
    "bundle",
    "bundle.runtime_hook",
    "rubicon.objc",
    "objc",
    "Quartz",
    "AppKit",
    "Foundation",
    "CoreFoundation",
]

for pkg in ("customtkinter", "easyocr", "tkinter"):
    try:
        pkg_datas, pkg_hidden, _pkg_binaries = collect_all(pkg)
        datas += pkg_datas
        hiddenimports += pkg_hidden
    except Exception as exc:
        print(f"collect_all({pkg}) skipped: {exc}")

try:
    datas += collect_data_files("torch", include_py_files=False)
except Exception:
    pass

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(spec_dir / "pyinstaller_hooks")],
    hooksconfig={},
    runtime_hooks=[str(spec_dir / "pyi_rthook.py")],
    excludes=["matplotlib", "pandas", "scipy", "notebook", "jupyter"],
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
    name="Sparx Solver Pro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Sparx Solver Pro",
)

app = BUNDLE(
    coll,
    name="Sparx Solver Pro.app",
    icon=None,
    bundle_identifier="com.sparx.solverpro",
    info_plist={
        "CFBundleName": "Sparx Solver Pro",
        "CFBundleDisplayName": "Sparx Solver Pro",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
        "NSScreenCaptureUsageDescription": (
            "Sparx Solver Pro captures the question area on your screen "
            "to read maths problems."
        ),
        "NSAccessibilityUsageDescription": (
            "Sparx Solver Pro needs Accessibility access to type answers into Sparx."
        ),
    },
)
