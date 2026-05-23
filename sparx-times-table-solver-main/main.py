import multiprocessing
import sys
import traceback
from pathlib import Path

_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_root))

CRASH_LOG = Path.home() / "Library" / "Logs" / "Sparx Solver Pro" / "crash.log"


def _write_crash_log() -> None:
    CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)
    CRASH_LOG.write_text(traceback.format_exc(), encoding="utf-8")


def main() -> None:
    from bundle.runtime_hook import configure_frozen_runtime

    configure_frozen_runtime()

    from ui.app import SparxProApp

    app = SparxProApp()
    app.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        main()
    except Exception:
        _write_crash_log()
        raise
