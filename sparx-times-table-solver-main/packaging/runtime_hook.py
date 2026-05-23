"""Bootstrap paths and logging when running inside a PyInstaller .app bundle."""
import logging
import os
import sys
from pathlib import Path


def configure_frozen_runtime() -> None:
    """Configure bundled resource paths and file logging for frozen builds."""
    if not getattr(sys, "frozen", False):
        return

    bundle_root = Path(getattr(sys, "_MEIPASS", ""))
    models_dir = bundle_root / "models" / "easyocr"
    if models_dir.is_dir():
        os.environ.setdefault("EASYOCR_MODULE_PATH", str(models_dir))

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
        logger.info("Frozen runtime configured (models=%s)", models_dir if models_dir.is_dir() else "missing")
