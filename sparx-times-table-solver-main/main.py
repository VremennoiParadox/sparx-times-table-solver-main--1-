import sys
from pathlib import Path

_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from packaging.runtime_hook import configure_frozen_runtime

configure_frozen_runtime()

from ui.app import SparxProApp

if __name__ == "__main__":
    app = SparxProApp()
    app.mainloop()
