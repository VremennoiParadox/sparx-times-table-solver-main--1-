"""Sparx Solver Pro — main application window.

Tabbed layout:
  Solver   — region picker, run controls, live stats, OCR preview, question log
  History  — past sessions with per-question drill-down and CSV export
  Settings — automation delays, OCR tuning, UI theme
"""
import logging
import queue
import sys
import tkinter as tk
import tkinter.filedialog as fd
import tkinter.messagebox as mb
from datetime import datetime
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from core.automator import Automator, SessionCallbacks, State
from core.capture import RegionSelector
from utils.config import AppConfig
from utils.history import HistoryManager, QuestionRecord, SessionRecord
from utils.macos_permissions import (
    PermissionStatus,
    get_status,
    open_accessibility_settings,
    open_screen_recording_settings,
    request_all,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def _confidence_colour(conf: float) -> str:
    if conf >= 0.75:
        return "#4ade80"   # green
    if conf >= 0.45:
        return "#facc15"   # yellow
    return "#f87171"       # red


# ──────────────────────────────────────────────────────────────────────────────
# Main application
# ──────────────────────────────────────────────────────────────────────────────

class SparxProApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.cfg = AppConfig.load()
        self.history = HistoryManager()
        self.automator = Automator()
        self.selector = RegionSelector()

        # Session state
        self._session: Optional[SessionRecord] = None
        self._session_start: Optional[datetime] = None
        self._completed = 0
        self._total = 0
        self._streak = 0
        self._best_streak = 0
        self._q_start: Optional[datetime] = None

        # Thread-safe event queue so automator callbacks safely update the UI
        self._ui_queue: queue.SimpleQueue = queue.SimpleQueue()

        self._build_window()
        self._build_ui()
        self._apply_saved_region()
        self._bind_hotkeys()
        self._poll_ui_queue()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._permissions_dialog: Optional[tk.Toplevel] = None
        # Draw main UI first; permissions after the window is on screen (avoids blank CTk on macOS).
        self.after(800, self._maybe_show_macos_permissions)

    def _maybe_show_macos_permissions(self) -> None:
        if sys.platform != "darwin":
            return

        self.update_idletasks()
        status = request_all()
        if status.all_granted:
            return
        self._show_macos_permissions_dialog(status)

    def _show_macos_permissions_dialog(self, status: PermissionStatus) -> None:
        if self._permissions_dialog is not None and self._permissions_dialog.winfo_exists():
            return

        dialog = tk.Toplevel(self)
        self._permissions_dialog = dialog
        dialog.title("Permissions Required")
        dialog.geometry("540x440")
        dialog.resizable(False, False)
        dialog.configure(bg="#1e1e2e")
        dialog.transient(self)
        # Do not use grab_set() — it can blank CustomTkinter windows on macOS.

        tk.Label(
            dialog,
            text="Sparx Solver Pro needs macOS permissions",
            font=("Helvetica", 15, "bold"),
            fg="#ffffff",
            bg="#1e1e2e",
        ).pack(pady=(18, 8))

        tk.Label(
            dialog,
            text=(
                "macOS may show popups — choose Allow or Open Settings.\n"
                "Turn ON both toggles for Sparx Solver Pro, then quit (Cmd+Q) and reopen."
            ),
            font=("Helvetica", 12),
            fg="#a8a8b8",
            bg="#1e1e2e",
            justify="left",
            wraplength=480,
        ).pack(padx=22, pady=(0, 14))

        screen_var = tk.StringVar()
        access_var = tk.StringVar()

        screen_label = tk.Label(
            dialog, textvariable=screen_var, anchor="w", font=("Helvetica", 13), bg="#1e1e2e"
        )
        screen_label.pack(fill="x", padx=22, pady=4)
        access_label = tk.Label(
            dialog, textvariable=access_var, anchor="w", font=("Helvetica", 13), bg="#1e1e2e"
        )
        access_label.pack(fill="x", padx=22, pady=(0, 12))

        def _refresh_labels(st: PermissionStatus) -> None:
            screen_var.set(
                "Screen Recording: granted"
                if st.screen_recording
                else "Screen Recording: not granted yet"
            )
            access_var.set(
                "Accessibility: granted"
                if st.accessibility
                else "Accessibility: not granted yet"
            )
            screen_label.configure(fg="#4ade80" if st.screen_recording else "#f87171")
            access_label.configure(fg="#4ade80" if st.accessibility else "#f87171")

        _refresh_labels(status)

        def _request_again() -> None:
            request_all()
            st = get_status()
            _refresh_labels(st)
            if st.all_granted:
                mb.showinfo(
                    "Permissions OK",
                    "All permissions granted. You can use the app now.",
                    parent=dialog,
                )

        btn_opts = {"font": ("Helvetica", 12), "bg": "#3d3d5c", "fg": "#ffffff", "pady": 6}
        tk.Button(
            dialog, text="Request permissions again", command=_request_again, **btn_opts
        ).pack(fill="x", padx=22, pady=3)
        tk.Button(
            dialog,
            text="Open Screen Recording settings",
            command=open_screen_recording_settings,
            **btn_opts,
        ).pack(fill="x", padx=22, pady=3)
        tk.Button(
            dialog,
            text="Open Accessibility settings",
            command=open_accessibility_settings,
            **btn_opts,
        ).pack(fill="x", padx=22, pady=3)

        def _close_dialog() -> None:
            self.cfg.macos_permissions_ack = True
            self.cfg.save()
            self._permissions_dialog = None
            dialog.destroy()

        tk.Button(
            dialog,
            text="Continue",
            command=_close_dialog,
            font=("Helvetica", 13, "bold"),
            bg="#2d8a4e",
            fg="#ffffff",
            pady=8,
        ).pack(fill="x", padx=22, pady=(14, 18))

        dialog.lift()
        dialog.focus_force()

    def _ensure_macos_permissions_for_action(self) -> bool:
        if sys.platform != "darwin":
            return True
        request_all()
        status = get_status()
        if status.all_granted:
            return True
        self._show_macos_permissions_dialog(status)
        mb.showwarning(
            "Permissions Required",
            "Enable Screen Recording and Accessibility for Sparx Solver Pro, "
            "then quit the app (Cmd+Q) and open it again.",
            parent=self,
        )
        return False

    # ──────────────────────────────────────────────────────────────────────
    # Window & UI construction
    # ──────────────────────────────────────────────────────────────────────

    def _build_window(self) -> None:
        ctk.set_appearance_mode(self.cfg.theme)
        try:
            ctk.set_default_color_theme(self.cfg.color_theme)
        except Exception:
            logger.warning("Theme %r unavailable, using default", self.cfg.color_theme)
        self.title("Sparx Solver Pro")
        self.geometry("980x680")
        self.minsize(820, 580)
        self.update_idletasks()

    def _build_ui(self) -> None:
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=12)

        for name in ("Solver", "History", "Settings"):
            self.tabview.add(name)

        self._build_solver_tab()
        self._build_history_tab()
        self._build_settings_tab()

    # ──────────────────────────────────────────────────────────────────────
    # SOLVER TAB
    # ──────────────────────────────────────────────────────────────────────

    def _build_solver_tab(self) -> None:
        tab = self.tabview.tab("Solver")

        # ── Left sidebar ──────────────────────────────────────────────────
        left = ctk.CTkFrame(tab, width=210, corner_radius=10)
        left.pack(side="left", fill="y", padx=(0, 8), pady=0)
        left.pack_propagate(False)

        # Region card
        self._add_card_title(left, "Question Region")
        self.region_label = ctk.CTkLabel(
            left, text="No region selected",
            font=ctk.CTkFont(size=11), text_color="gray", wraplength=180
        )
        self.region_label.pack(padx=10, pady=(0, 4))
        self.select_btn = ctk.CTkButton(
            left, text="Select Region", height=32,
            command=self._begin_region_selection
        )
        self.select_btn.pack(padx=10, pady=(0, 10), fill="x")

        # Rounds card
        self._add_card_title(left, "Rounds")
        self.rounds_var = tk.StringVar(value=str(self.cfg.rounds))
        self.rounds_entry = ctk.CTkEntry(
            left, textvariable=self.rounds_var, justify="center", height=32
        )
        self.rounds_entry.pack(padx=10, pady=(0, 10), fill="x")

        # Controls card
        self._add_card_title(left, "Controls")
        self.start_btn = ctk.CTkButton(
            left, text="▶  Start", height=34,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._start_session, state="disabled"
        )
        self.start_btn.pack(padx=10, pady=(0, 4), fill="x")

        self.pause_btn = ctk.CTkButton(
            left, text="⏸  Pause", height=34,
            fg_color="#a07830", hover_color="#7d5e26",
            command=self._toggle_pause, state="disabled"
        )
        self.pause_btn.pack(padx=10, pady=(0, 4), fill="x")

        self.stop_btn = ctk.CTkButton(
            left, text="■  Stop", height=34,
            fg_color="#8b2424", hover_color="#6b1b1b",
            command=self._stop_session, state="disabled"
        )
        self.stop_btn.pack(padx=10, pady=(0, 10), fill="x")

        # Hotkey hint
        ctk.CTkLabel(
            left, text="Ctrl+Enter  Start\nSpace  Pause / Resume\nEsc  Stop",
            font=ctk.CTkFont(size=10), text_color="gray", justify="left"
        ).pack(padx=14, pady=4, anchor="w")

        # Status
        self.status_label = ctk.CTkLabel(
            left, text="Ready", font=ctk.CTkFont(size=11), text_color="gray"
        )
        self.status_label.pack(padx=10, pady=(8, 10))

        # ── Right panel ───────────────────────────────────────────────────
        right = ctk.CTkFrame(tab, corner_radius=10)
        right.pack(side="right", fill="both", expand=True)

        # Stats row
        stats_row = ctk.CTkFrame(right, fg_color="transparent")
        stats_row.pack(fill="x", padx=10, pady=(10, 4))

        self._stat_vars: dict[str, tk.StringVar] = {}
        for key, label, init in [
            ("progress", "Progress", "0 / 0"),
            ("rate",     "Q / min",  "—"),
            ("elapsed",  "Elapsed",  "0:00"),
            ("eta",      "ETA",      "—"),
            ("streak",   "Streak",   "0"),
        ]:
            card = ctk.CTkFrame(stats_row, corner_radius=8)
            card.pack(side="left", expand=True, fill="both", padx=4)
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=10), text_color="gray").pack(pady=(6, 0))
            var = tk.StringVar(value=init)
            self._stat_vars[key] = var
            ctk.CTkLabel(card, textvariable=var, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 6))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(right, height=8)
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 8))
        self.progress_bar.set(0)

        # Lower split: OCR preview | Question log
        lower = ctk.CTkFrame(right, fg_color="transparent")
        lower.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # OCR preview pane
        preview_pane = ctk.CTkFrame(lower, corner_radius=8, width=260)
        preview_pane.pack(side="left", fill="both", padx=(0, 6))
        preview_pane.pack_propagate(False)

        ctk.CTkLabel(preview_pane, text="OCR Preview", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(8, 4))

        self.preview_canvas = tk.Canvas(
            preview_pane, bg="#1a1a2e", highlightthickness=0, height=120
        )
        self.preview_canvas.pack(fill="both", expand=True, padx=6)
        self._preview_photo: Optional[ImageTk.PhotoImage] = None

        self.detected_var = tk.StringVar(value="Detected: —")
        ctk.CTkLabel(
            preview_pane, textvariable=self.detected_var,
            font=ctk.CTkFont(family="Courier", size=12), text_color="#00ff88"
        ).pack(pady=(4, 8))

        self.answer_var = tk.StringVar(value="Answer: —")
        ctk.CTkLabel(
            preview_pane, textvariable=self.answer_var,
            font=ctk.CTkFont(family="Courier", size=13, weight="bold"), text_color="#60a5fa"
        ).pack(pady=(0, 8))

        # Question log pane
        log_pane = ctk.CTkFrame(lower, corner_radius=8)
        log_pane.pack(side="right", fill="both", expand=True)

        ctk.CTkLabel(log_pane, text="Question Log", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(8, 4))

        self.question_log = ctk.CTkTextbox(
            log_pane, state="disabled",
            font=ctk.CTkFont(family="Courier", size=12)
        )
        self.question_log.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        # Configure colour tags (applied via the underlying Text widget)
        self.question_log._textbox.tag_config("high",   foreground="#4ade80")
        self.question_log._textbox.tag_config("medium", foreground="#facc15")
        self.question_log._textbox.tag_config("low",    foreground="#f87171")
        self.question_log._textbox.tag_config("index",  foreground="#94a3b8")

    # ──────────────────────────────────────────────────────────────────────
    # HISTORY TAB
    # ──────────────────────────────────────────────────────────────────────

    def _build_history_tab(self) -> None:
        tab = self.tabview.tab("History")

        # Summary bar
        summary = ctk.CTkFrame(tab, corner_radius=8)
        summary.pack(fill="x", padx=10, pady=(10, 6))

        self._history_summary_vars: dict[str, tk.StringVar] = {}
        for key, label in [
            ("total_sessions", "Sessions"),
            ("total_questions", "All-time Q"),
            ("best_rate", "Best Q/min"),
        ]:
            card = ctk.CTkFrame(summary, fg_color="transparent")
            card.pack(side="left", expand=True, fill="both", padx=8, pady=6)
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=10), text_color="gray").pack()
            var = tk.StringVar(value="—")
            self._history_summary_vars[key] = var
            ctk.CTkLabel(card, textvariable=var, font=ctk.CTkFont(size=16, weight="bold")).pack()

        # Split: session list | question detail
        split = ctk.CTkFrame(tab, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Session list
        session_pane = ctk.CTkFrame(split, corner_radius=8, width=280)
        session_pane.pack(side="left", fill="y", padx=(0, 6))
        session_pane.pack_propagate(False)

        ctk.CTkLabel(session_pane, text="Sessions", font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(8, 4))

        self.session_scroll = ctk.CTkScrollableFrame(session_pane, fg_color="transparent")
        self.session_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        # Question detail
        detail_pane = ctk.CTkFrame(split, corner_radius=8)
        detail_pane.pack(side="right", fill="both", expand=True)

        detail_header = ctk.CTkFrame(detail_pane, fg_color="transparent")
        detail_header.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            detail_header, text="Question Detail",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")

        self.export_btn = ctk.CTkButton(
            detail_header, text="Export CSV", width=100, height=28,
            command=self._export_session
        )
        self.export_btn.pack(side="right")

        self.detail_box = ctk.CTkTextbox(
            detail_pane, state="disabled",
            font=ctk.CTkFont(family="Courier", size=12)
        )
        self.detail_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._selected_session: Optional[SessionRecord] = None
        self._populate_history()

    # ──────────────────────────────────────────────────────────────────────
    # SETTINGS TAB
    # ──────────────────────────────────────────────────────────────────────

    def _build_settings_tab(self) -> None:
        tab = self.tabview.tab("Settings")

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # ── Automation ────────────────────────────────────────────────────
        self._add_card_title(scroll, "Automation")

        self._s_round_delay = self._add_slider(
            scroll, "Round delay (s)", 0.3, 2.0, self.cfg.round_delay, resolution=0.05
        )
        self._s_repeat_delay = self._add_slider(
            scroll, "Repeat delay (s)", 0.05, 1.0, self.cfg.repeat_delay, resolution=0.05
        )
        self._s_type_delay = self._add_slider(
            scroll, "Type delay (s)", 0.01, 0.2, self.cfg.type_delay, resolution=0.01
        )

        # ── OCR ───────────────────────────────────────────────────────────
        self._add_card_title(scroll, "OCR")

        self._s_ocr_conf = self._add_slider(
            scroll, "Min confidence", 0.1, 0.9, self.cfg.ocr_confidence, resolution=0.05
        )

        # ── Appearance ────────────────────────────────────────────────────
        self._add_card_title(scroll, "Appearance")

        theme_row = ctk.CTkFrame(scroll, fg_color="transparent")
        theme_row.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkLabel(theme_row, text="Theme", width=140, anchor="w").pack(side="left")
        self._theme_var = tk.StringVar(value=self.cfg.theme)
        ctk.CTkOptionMenu(
            theme_row, variable=self._theme_var, values=["dark", "light", "system"],
            command=lambda v: ctk.set_appearance_mode(v)
        ).pack(side="right")

        color_row = ctk.CTkFrame(scroll, fg_color="transparent")
        color_row.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkLabel(color_row, text="Accent colour", width=140, anchor="w").pack(side="left")
        self._color_var = tk.StringVar(value=self.cfg.color_theme)
        ctk.CTkOptionMenu(
            color_row, variable=self._color_var, values=["blue", "dark-blue", "green"]
        ).pack(side="right")

        # Save button
        ctk.CTkButton(scroll, text="Save Settings", height=36, command=self._save_settings).pack(
            padx=10, pady=(16, 4), fill="x"
        )
        ctk.CTkButton(
            scroll, text="Reset to Defaults", height=32,
            fg_color="transparent", border_width=1,
            command=self._reset_settings
        ).pack(padx=10, pady=(0, 16), fill="x")

    # ──────────────────────────────────────────────────────────────────────
    # UI helpers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _add_card_title(parent: ctk.CTkBaseClass, text: str) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        ).pack(fill="x", padx=10, pady=(12, 4))

    @staticmethod
    def _add_slider(
        parent: ctk.CTkBaseClass,
        label: str,
        from_: float,
        to: float,
        init: float,
        resolution: float = 0.1,
    ) -> ctk.CTkSlider:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 6))

        val_var = tk.StringVar(value=f"{init:.2f}")
        ctk.CTkLabel(row, text=label, width=150, anchor="w").pack(side="left")
        ctk.CTkLabel(row, textvariable=val_var, width=40, anchor="e").pack(side="right")

        slider = ctk.CTkSlider(row, from_=from_, to=to, number_of_steps=int((to - from_) / resolution))
        slider.set(init)
        slider.pack(side="left", fill="x", expand=True, padx=8)
        slider.configure(command=lambda v: val_var.set(f"{v:.2f}"))
        slider._val_var = val_var  # type: ignore[attr-defined]

        return slider

    # ──────────────────────────────────────────────────────────────────────
    # Region selection
    # ──────────────────────────────────────────────────────────────────────

    def _apply_saved_region(self) -> None:
        if self.cfg.region:
            x1, y1, x2, y2 = self.cfg.region
            self.region_label.configure(
                text=f"({x1}, {y1}) → ({x2}, {y2})\n{x2-x1} × {y2-y1} px",
                text_color="white",
            )
            self.start_btn.configure(state="normal")

    def _begin_region_selection(self) -> None:
        if not self._ensure_macos_permissions_for_action():
            return
        self.withdraw()
        self.after(150, self._do_region_selection)

    def _do_region_selection(self) -> None:
        region = self.selector.select(self)
        self.deiconify()
        self.lift()

        if region:
            self.cfg.region = region
            self.cfg.save()
            x1, y1, x2, y2 = region
            self.region_label.configure(
                text=f"({x1}, {y1}) → ({x2}, {y2})\n{x2-x1} × {y2-y1} px",
                text_color="white",
            )
            self.start_btn.configure(state="normal")
            self._set_status("Region selected — ready to start.")
        else:
            self._set_status("Region selection cancelled.")

    # ──────────────────────────────────────────────────────────────────────
    # Session control
    # ──────────────────────────────────────────────────────────────────────

    def _start_session(self) -> None:
        if self.automator.state in (State.RUNNING, State.PAUSED):
            return
        if not self._ensure_macos_permissions_for_action():
            return
        if not self.cfg.region:
            mb.showwarning("No Region", "Please select a question region first.")
            return

        try:
            rounds = int(self.rounds_var.get())
            if rounds < 1:
                raise ValueError
        except ValueError:
            mb.showwarning("Invalid Rounds", "Please enter a positive integer for rounds.")
            return

        # Reset session state
        self._completed = 0
        self._total = rounds
        self._streak = 0
        self._best_streak = 0
        self._session_start = datetime.now()
        self._q_start = datetime.now()
        self._clear_question_log()
        self.progress_bar.set(0)
        self._reset_stats(rounds)

        # Create session record
        self._session = SessionRecord(
            id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            start_time=self._session_start.isoformat(),
            end_time=None,
            target_rounds=rounds,
            completed_rounds=0,
        )

        cb = SessionCallbacks(
            on_question=self._cb_question,
            on_progress=self._cb_progress,
            on_preview=self._cb_preview,
            on_state_change=self._cb_state_change,
            on_error=self._cb_error,
            on_complete=self._cb_complete,
        )

        self.automator.start(
            region=self.cfg.region,
            rounds=rounds,
            cb=cb,
            round_delay=self.cfg.round_delay,
            repeat_delay=self.cfg.repeat_delay,
            type_delay=self.cfg.type_delay,
            ocr_confidence=self.cfg.ocr_confidence,
        )

        self._update_stats_loop()

    def _toggle_pause(self) -> None:
        if self.automator.state == State.RUNNING:
            self.automator.pause(self._make_null_cb())
        elif self.automator.state == State.PAUSED:
            self.automator.resume(self._make_null_cb())

    def _stop_session(self) -> None:
        if self.automator.state in (State.RUNNING, State.PAUSED):
            self.automator.stop(self._make_null_cb())

    def _make_null_cb(self) -> SessionCallbacks:
        """Callbacks that only handle state change (for pause/stop from UI)."""
        return SessionCallbacks(on_state_change=self._cb_state_change)

    # ──────────────────────────────────────────────────────────────────────
    # Automator callbacks (called from worker thread → enqueue for UI thread)
    # ──────────────────────────────────────────────────────────────────────

    def _cb_question(self, expr: str, answer: str, confidence: float, elapsed_ms: int) -> None:
        self._ui_queue.put(("question", expr, answer, confidence, elapsed_ms))

    def _cb_progress(self, completed: int, total: int) -> None:
        self._ui_queue.put(("progress", completed, total))

    def _cb_preview(self, img: object) -> None:
        self._ui_queue.put(("preview", img))

    def _cb_state_change(self, state: State) -> None:
        self._ui_queue.put(("state", state))

    def _cb_error(self, msg: str) -> None:
        self._ui_queue.put(("error", msg))

    def _cb_complete(self) -> None:
        self._ui_queue.put(("complete",))

    # ──────────────────────────────────────────────────────────────────────
    # UI queue consumer (runs in main thread via after())
    # ──────────────────────────────────────────────────────────────────────

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                item = self._ui_queue.get_nowait()
                self._handle_ui_event(item)
        except queue.Empty:
            pass
        self.after(50, self._poll_ui_queue)

    def _handle_ui_event(self, item: tuple) -> None:
        kind = item[0]

        if kind == "question":
            _, expr, answer, confidence, elapsed_ms = item
            self._completed += 1
            self._streak += 1
            self._best_streak = max(self._streak, self._best_streak)
            self._stat_vars["streak"].set(str(self._streak))
            self.detected_var.set(f"Detected: {expr}")
            self.answer_var.set(f"Answer: {answer}")
            self._append_question_log(self._completed, expr, answer, confidence)
            if self._session:
                self._session.questions.append(
                    QuestionRecord(
                        expression=expr,
                        answer=answer,
                        elapsed_ms=elapsed_ms,
                        confidence=confidence,
                    )
                )

        elif kind == "progress":
            _, completed, total = item
            frac = completed / total if total else 0
            self.progress_bar.set(frac)
            self._stat_vars["progress"].set(f"{completed} / {total}")

        elif kind == "preview":
            _, img = item
            self._update_preview(img)

        elif kind == "state":
            _, state = item
            self._on_state_change(state)

        elif kind == "error":
            _, msg = item
            self._set_status(f"Error: {msg}")
            logger.error("Automator error: %s", msg)

        elif kind == "complete":
            self._on_session_complete()

    # ──────────────────────────────────────────────────────────────────────
    # UI update helpers
    # ──────────────────────────────────────────────────────────────────────

    def _update_preview(self, img: object) -> None:
        try:
            from PIL import Image as PILImage
            # Work on a copy so thumbnail() doesn't mutate the original
            pil_img: PILImage.Image = img.copy()  # type: ignore[union-attr]
            self.preview_canvas.update_idletasks()
            canvas_w = self.preview_canvas.winfo_width()
            canvas_h = self.preview_canvas.winfo_height()
            # Fallback dimensions if the canvas hasn't been laid out yet
            if canvas_w < 10:
                canvas_w = 240
            if canvas_h < 10:
                canvas_h = 120
            pil_img.thumbnail((canvas_w, canvas_h), PILImage.LANCZOS)
            self._preview_photo = ImageTk.PhotoImage(pil_img)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(
                canvas_w // 2, canvas_h // 2,
                anchor="center", image=self._preview_photo
            )
        except Exception as exc:
            logger.debug("Preview update failed: %s", exc)

    def _append_question_log(
        self, idx: int, expr: str, answer: str, confidence: float
    ) -> None:
        self.question_log.configure(state="normal")
        tb = self.question_log._textbox
        colour_tag = (
            "high" if confidence >= 0.75
            else "medium" if confidence >= 0.45
            else "low"
        )
        tb.insert("end", f"{idx:>3}. ", "index")
        tb.insert("end", f"{expr} = {answer}", colour_tag)
        tb.insert("end", f"  ({confidence:.0%})\n", "index")
        self.question_log.configure(state="disabled")
        self.question_log._textbox.see("end")

    def _clear_question_log(self) -> None:
        self.question_log.configure(state="normal")
        self.question_log.delete("1.0", "end")
        self.question_log.configure(state="disabled")

    def _reset_stats(self, total: int) -> None:
        self._stat_vars["progress"].set(f"0 / {total}")
        self._stat_vars["rate"].set("—")
        self._stat_vars["elapsed"].set("0:00")
        self._stat_vars["eta"].set("—")
        self._stat_vars["streak"].set("0")

    def _update_stats_loop(self) -> None:
        if self.automator.state not in (State.RUNNING, State.PAUSED):
            return
        if self._session_start:
            elapsed = (datetime.now() - self._session_start).total_seconds()
            self._stat_vars["elapsed"].set(_fmt_duration(elapsed))
            n = self._completed
            if n > 0 and elapsed > 0:
                rate = n / elapsed * 60
                self._stat_vars["rate"].set(f"{rate:.1f}")
                remaining = self._total - n
                if rate > 0:
                    eta = remaining / rate * 60
                    self._stat_vars["eta"].set(_fmt_duration(eta))
        self.after(500, self._update_stats_loop)

    def _on_state_change(self, state: State) -> None:
        if state == State.RUNNING:
            self.start_btn.configure(state="disabled")
            self.pause_btn.configure(state="normal", text="⏸  Pause")
            self.stop_btn.configure(state="normal")
            self.select_btn.configure(state="disabled")
            self._set_status("Running…")

        elif state == State.PAUSED:
            self.pause_btn.configure(text="▶  Resume")
            self._set_status("Paused")

        elif state == State.IDLE:
            self.start_btn.configure(state="normal" if self.cfg.region else "disabled")
            self.pause_btn.configure(state="disabled", text="⏸  Pause")
            self.stop_btn.configure(state="disabled")
            self.select_btn.configure(state="normal")

    def _on_session_complete(self) -> None:
        if self._session:
            self._session.end_time = datetime.now().isoformat()
            self._session.completed_rounds = self._completed
            self.history.add_session(self._session)
            self._session = None
        rate_str = self._stat_vars["rate"].get()
        self._set_status(f"Session complete — {self._completed} questions  ({rate_str} q/min)")
        self._populate_history()
        self._streak = 0

    def _set_status(self, msg: str) -> None:
        self.status_label.configure(text=msg)

    # ──────────────────────────────────────────────────────────────────────
    # History tab helpers
    # ──────────────────────────────────────────────────────────────────────

    def _populate_history(self) -> None:
        # Update summary stats
        sessions = self.history.get_recent()
        total_q = self.history.total_questions()
        best_r = self.history.lifetime_best_rate()
        self._history_summary_vars["total_sessions"].set(str(len(self.history.sessions)))
        self._history_summary_vars["total_questions"].set(str(total_q))
        self._history_summary_vars["best_rate"].set(f"{best_r:.1f}" if best_r else "—")

        # Clear session list
        for w in self.session_scroll.winfo_children():
            w.destroy()

        for sess in sessions:
            self._add_session_card(sess)

    def _add_session_card(self, sess: SessionRecord) -> None:
        card = ctk.CTkFrame(self.session_scroll, corner_radius=6)
        card.pack(fill="x", pady=3)

        dt = datetime.fromisoformat(sess.start_time).strftime("%b %d  %H:%M")
        qpm = f"{sess.questions_per_minute:.1f} q/min" if sess.duration_seconds > 0 else "—"
        dur = _fmt_duration(sess.duration_seconds)

        ctk.CTkLabel(card, text=dt, font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(
            fill="x", padx=8, pady=(6, 0)
        )
        ctk.CTkLabel(
            card,
            text=f"{sess.completed_rounds}/{sess.target_rounds} rounds  ·  {dur}  ·  {qpm}",
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w"
        ).pack(fill="x", padx=8, pady=(0, 6))

        card.bind("<Button-1>", lambda _e, s=sess: self._show_session_detail(s))
        for child in card.winfo_children():
            child.bind("<Button-1>", lambda _e, s=sess: self._show_session_detail(s))

    def _show_session_detail(self, sess: SessionRecord) -> None:
        self._selected_session = sess
        self.detail_box.configure(state="normal")
        self.detail_box.delete("1.0", "end")

        dt = datetime.fromisoformat(sess.start_time).strftime("%Y-%m-%d  %H:%M:%S")
        self.detail_box.insert("end", f"Session: {dt}\n")
        self.detail_box.insert(
            "end",
            f"Rounds: {sess.completed_rounds}/{sess.target_rounds}  |  "
            f"Duration: {_fmt_duration(sess.duration_seconds)}  |  "
            f"Rate: {sess.questions_per_minute:.1f} q/min\n"
        )
        self.detail_box.insert("end", "─" * 60 + "\n")
        self.detail_box.insert("end", f"{'#':>4}  {'Expression':<20}  {'Answer':>8}  {'Conf':>6}  {'ms':>6}\n")
        self.detail_box.insert("end", "─" * 60 + "\n")

        for i, q in enumerate(sess.questions, 1):
            conf_str = f"{q.confidence:.0%}" if q.confidence > 0 else "—"
            self.detail_box.insert(
                "end",
                f"{i:>4}  {q.expression:<20}  {q.answer:>8}  {conf_str:>6}  {q.elapsed_ms:>6}\n"
            )

        self.detail_box.configure(state="disabled")

    def _export_session(self) -> None:
        if not self._selected_session:
            mb.showinfo("No Session", "Click a session in the list to select it first.")
            return
        path = fd.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"sparx_session_{self._selected_session.id}.csv",
        )
        if path:
            self._selected_session.export_csv(path)
            mb.showinfo("Exported", f"Session saved to:\n{path}")

    # ──────────────────────────────────────────────────────────────────────
    # Settings tab helpers
    # ──────────────────────────────────────────────────────────────────────

    def _save_settings(self) -> None:
        self.cfg.round_delay = round(self._s_round_delay.get(), 2)
        self.cfg.repeat_delay = round(self._s_repeat_delay.get(), 2)
        self.cfg.type_delay = round(self._s_type_delay.get(), 2)
        self.cfg.ocr_confidence = round(self._s_ocr_conf.get(), 2)
        self.cfg.theme = self._theme_var.get()
        self.cfg.color_theme = self._color_var.get()
        self.cfg.rounds = int(self.rounds_var.get()) if self.rounds_var.get().isdigit() else 25
        self.cfg.save()
        ctk.set_appearance_mode(self.cfg.theme)
        mb.showinfo("Settings Saved", "Your settings have been saved.")

    def _reset_settings(self) -> None:
        defaults = AppConfig()
        self._s_round_delay.set(defaults.round_delay)
        self._s_repeat_delay.set(defaults.repeat_delay)
        self._s_type_delay.set(defaults.type_delay)
        self._s_ocr_conf.set(defaults.ocr_confidence)
        self._theme_var.set(defaults.theme)
        self._color_var.set(defaults.color_theme)
        self.rounds_var.set(str(defaults.rounds))

    # ──────────────────────────────────────────────────────────────────────
    # Keyboard shortcuts
    # ──────────────────────────────────────────────────────────────────────

    def _bind_hotkeys(self) -> None:
        self.bind("<Control-Return>", lambda _e: self._start_session())
        self.bind("<Escape>", lambda _e: self._stop_session())
        self.bind("<space>", lambda _e: self._toggle_pause())

    # ──────────────────────────────────────────────────────────────────────
    # Close
    # ──────────────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        if self.automator.state in (State.RUNNING, State.PAUSED):
            if not mb.askyesno("Quit", "A session is running. Stop it and quit?"):
                return
            self.automator.stop(self._make_null_cb())
        self.destroy()
