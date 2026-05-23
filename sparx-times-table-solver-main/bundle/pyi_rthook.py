"""PyInstaller runtime hook — runs before main.py (avoids import-order crashes)."""
import os
import sys

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    meipass = sys._MEIPASS
    if meipass not in sys.path:
        sys.path.insert(0, meipass)
    models = os.path.join(meipass, "models", "easyocr")
    if os.path.isdir(models):
        os.environ.setdefault("EASYOCR_MODULE_PATH", models)
