"""Automation engine with full pause/resume support.

Key improvements over the original:
- State machine (IDLE → RUNNING ↔ PAUSED → STOPPED/IDLE)
- Pause/Resume via threading.Event instead of kill-and-restart
- Typed callback protocol so the UI gets rich progress updates
- OCR preview callback so the user can see what the bot is reading
- Per-question timing for analytics
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional, Tuple

import pyautogui

from .capture import capture_region
from .ocr import OCREngine
from .solver import MathSolver

logger = logging.getLogger(__name__)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.0  # We manage our own delays


class State(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class SessionCallbacks:
    """Callbacks fired by the automator from its worker thread.

    All UI code must schedule updates via `widget.after(0, fn)` rather than
    touching widgets directly from these callbacks.
    """
    on_question: Callable[[str, str, float, int], None] = field(
        default=lambda *_: None
    )
    """Called with (expression, answer, confidence, elapsed_ms) after each submission."""

    on_progress: Callable[[int, int], None] = field(default=lambda *_: None)
    """Called with (completed, total) after each round."""

    on_preview: Callable[[object], None] = field(default=lambda _: None)
    """Called with a PIL Image after each capture."""

    on_state_change: Callable[["State"], None] = field(default=lambda _: None)
    on_error: Callable[[str], None] = field(default=lambda _: None)
    on_complete: Callable[[], None] = field(default=lambda: None)


class Automator:
    def __init__(self) -> None:
        self._ocr = OCREngine()
        self._solver = MathSolver()
        self._state = State.IDLE
        self._thread: Optional[threading.Thread] = None
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_event = threading.Event()

    @property
    def state(self) -> State:
        return self._state

    def _set_state(self, state: State, cb: SessionCallbacks) -> None:
        self._state = state
        cb.on_state_change(state)

    # ------------------------------------------------------------------
    # Public control API
    # ------------------------------------------------------------------
    def start(
        self,
        region: Tuple[int, int, int, int],
        rounds: int,
        cb: SessionCallbacks,
        round_delay: float = 0.8,
        repeat_delay: float = 0.25,
        type_delay: float = 0.05,
        ocr_confidence: float = 0.3,
    ) -> None:
        if self._state in (State.RUNNING, State.PAUSED):
            return
        self._stop_event.clear()
        self._pause_event.set()
        self._thread = threading.Thread(
            target=self._run,
            args=(region, rounds, cb, round_delay, repeat_delay, type_delay, ocr_confidence),
            daemon=True,
        )
        self._thread.start()

    def pause(self, cb: SessionCallbacks) -> None:
        if self._state == State.RUNNING:
            self._pause_event.clear()
            self._set_state(State.PAUSED, cb)

    def resume(self, cb: SessionCallbacks) -> None:
        if self._state == State.PAUSED:
            self._pause_event.set()
            self._set_state(State.RUNNING, cb)

    def stop(self, cb: SessionCallbacks) -> None:
        self._stop_event.set()
        self._pause_event.set()  # unblock if currently paused

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------
    def _run(
        self,
        region: Tuple[int, int, int, int],
        rounds: int,
        cb: SessionCallbacks,
        round_delay: float,
        repeat_delay: float,
        type_delay: float,
        ocr_confidence: float,
    ) -> None:
        self._set_state(State.RUNNING, cb)
        completed = 0
        last_expr: Optional[str] = None

        try:
            while completed < rounds and not self._stop_event.is_set():
                # Failsafe: mouse at top-left corner
                mx, my = pyautogui.position()
                if mx == 0 and my == 0:
                    cb.on_error("Failsafe triggered — mouse moved to (0, 0)")
                    break

                # Block here if paused
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break

                # Capture + OCR
                try:
                    q_start = datetime.now()
                    img = capture_region(region)
                    cb.on_preview(img)
                    text, confidence, _ = self._ocr.extract(img, ocr_confidence)
                except Exception as exc:
                    logger.error("Capture/OCR error: %s", exc)
                    cb.on_error(f"OCR error: {exc}")
                    time.sleep(repeat_delay)
                    continue

                # Solve
                answer, eq_type = self._solver.solve(text)
                if answer is None:
                    pyautogui.press("enter")
                    time.sleep(repeat_delay)
                    continue

                normalized = self._solver.normalize(text)

                # Skip duplicate frames (same question still on screen)
                if normalized == last_expr:
                    time.sleep(repeat_delay)
                    continue

                last_expr = normalized
                elapsed_ms = int((datetime.now() - q_start).total_seconds() * 1000)

                # Type and submit
                pyautogui.typewrite(answer, interval=type_delay)
                pyautogui.press("enter")

                completed += 1
                cb.on_question(normalized, answer, confidence, elapsed_ms)
                cb.on_progress(completed, rounds)

                time.sleep(round_delay)

        except pyautogui.FailSafeException:
            cb.on_error("PyAutoGUI failsafe triggered")
        except Exception as exc:
            logger.exception("Session crashed: %s", exc)
            cb.on_error(str(exc))
        finally:
            self._set_state(State.IDLE, cb)
            cb.on_complete()
