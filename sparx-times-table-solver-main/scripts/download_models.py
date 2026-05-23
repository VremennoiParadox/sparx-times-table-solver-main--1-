#!/usr/bin/env python3
"""Download EasyOCR models and stage them for PyInstaller bundling."""
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STAGE_DIR = PROJECT_ROOT / "bundle" / "models" / "easyocr"
EASYOCR_MODEL_DIR = Path.home() / ".EasyOCR" / "model"


def main() -> None:
    print("Downloading EasyOCR English models (CPU)...")
    import easyocr

    easyocr.Reader(["en"], gpu=False)

    if not EASYOCR_MODEL_DIR.is_dir():
        print(f"ERROR: Models not found at {EASYOCR_MODEL_DIR}", file=sys.stderr)
        sys.exit(1)

    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)

    STAGE_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(EASYOCR_MODEL_DIR, STAGE_DIR)
    print(f"Staged {len(list(STAGE_DIR.rglob('*')))} files to {STAGE_DIR}")


if __name__ == "__main__":
    main()
