"""Bootstrap paths and logging when running inside a PyInstaller .app bundle."""
import logging
import os
import sys
from pathlib import Path


def configure_customtkinter() -> None:
    """Point CustomTkinter at bundled theme/font assets (required for PyInstaller)."""
    if not getattr(sys, "frozen", False):
        return

    import customtkinter as ctk

    base = Path(sys._MEIPASS) / "customtkinter"
    if not base.is_dir():
        logging.getLogger(__name__).warning(
            "Bundled customtkinter assets missing at %s", base
        )
        return

    # CTk resolves themes/fonts relative to this directory.
    ctk_dir = str(base)
    if hasattr(ctk, "customtkinter_directory"):
        ctk.customtkinter_directory = ctk_dir

    os.environ.setdefault("CUSTOMTKINTER_DISABLE_FONT_PRELOAD", "1")

    for theme_name in ("blue", "dark-blue", "green"):
        theme_path = base / "assets" / "themes" / f"{theme_name}.json"
        if theme_path.is_file():
            try:
                ctk.set_default_color_theme(str(theme_path))
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "Could not load theme %s: %s", theme_path, exc
                )
            break

    logging.getLogger(__name__).info("CustomTkinter configured from %s", ctk_dir)


def configure_frozen_runtime() -> None:
    """Configure bundled resource paths and file logging for frozen builds."""
    if not getattr(sys, "frozen", False):
        return

    bundle_root = Path(getattr(sys, "_MEIPASS", ""))
    models_dir = bundle_root / "models" / "easyocr"
    if models_dir.is_dir():
        os.environ.setdefault("EASYOCR_MODULE_PATH", str(models_dir))

    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

    if sys.platform == "darwin":
        log_dir = Path.home() / "Library" / "Logs" / "Sparx Solver Pro"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            handlers=[logging.FileHandler(log_file)],
            force=True,
        )
        logger = logging.getLogger(__name__)
        logger.info(
            "Frozen runtime configured (models=%s)",
            models_dir if models_dir.is_dir() else "missing",
        )
