#!/usr/bin/env python3
"""Quick check that solver/OCR pipeline logic still works (no GUI)."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.solver import MathSolver


def main() -> None:
    solver = MathSolver()
    cases = [
        ("3x4", "12", "expression"),
        ("2x+3=7", "2", "equation"),
        ("10+5", "15", "expression"),
    ]
    failed = 0
    for raw, expected, eq_type in cases:
        answer, got_type = solver.solve(raw)
        ok = answer == expected and got_type == eq_type
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {raw!r} -> {answer!r} ({got_type})  expected {expected!r}")
        if not ok:
            failed += 1

    print()
    print("Capture, OCR, and automation require macOS permissions + display — not tested here.")
    print("UI tabs: Solver (region/start), History, Settings — unchanged.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
