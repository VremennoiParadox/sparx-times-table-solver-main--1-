"""Screen capture utilities with an interactive drag-to-select overlay."""
import tkinter as tk
from typing import Optional, Tuple

from PIL import Image, ImageGrab, ImageTk


class RegionSelector:
    """Interactive drag-to-select screen region picker.

    Improvements over the original 2-button click approach:
    - Single intuitive drag gesture
    - Full-screen screenshot as background so the user sees exactly what they're selecting
    - Live size readout while dragging
    """

    def __init__(self) -> None:
        self.region: Optional[Tuple[int, int, int, int]] = None

    def select(self, parent: tk.Misc) -> Optional[Tuple[int, int, int, int]]:
        """Show the fullscreen overlay and return the chosen region, or None if cancelled."""
        self.region = None

        # Logical screen dimensions from tkinter (what the OS reports to apps)
        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()

        # On macOS Retina displays ImageGrab returns a 2× physical-pixel image.
        # Resizing it to the logical dimensions makes it fill the canvas correctly
        # and keeps drag coordinates in the same logical-pixel space as ImageGrab.grab(bbox=…).
        screenshot = ImageGrab.grab()
        if screenshot.width != sw or screenshot.height != sh:
            screenshot = screenshot.resize((sw, sh), Image.LANCZOS)

        overlay = tk.Toplevel(parent)
        overlay.attributes("-fullscreen", True)
        overlay.attributes("-topmost", True)
        overlay.config(cursor="crosshair")

        photo = ImageTk.PhotoImage(screenshot, master=overlay)
        canvas = tk.Canvas(overlay, highlightthickness=0, width=sw, height=sh)
        canvas.pack(fill="both", expand=True)
        canvas.create_image(0, 0, anchor="nw", image=photo)

        # Semi-transparent top bar with instructions
        canvas.create_rectangle(0, 0, sw, 44, fill="#000000", stipple="gray50")
        canvas.create_text(
            sw // 2, 22,
            text="Drag to select the question area.  Press Esc to cancel.",
            fill="white",
            font=("Arial", 14),
        )

        start_x = start_y = 0
        rect_id: list = [None]
        size_id: list = [None]

        def on_press(event: tk.Event) -> None:
            nonlocal start_x, start_y
            start_x, start_y = event.x, event.y
            if rect_id[0]:
                canvas.delete(rect_id[0])
            if size_id[0]:
                canvas.delete(size_id[0])

        def on_drag(event: tk.Event) -> None:
            if rect_id[0]:
                canvas.delete(rect_id[0])
            if size_id[0]:
                canvas.delete(size_id[0])
            x1 = min(start_x, event.x)
            y1 = min(start_y, event.y)
            x2 = max(start_x, event.x)
            y2 = max(start_y, event.y)
            rect_id[0] = canvas.create_rectangle(
                x1, y1, x2, y2, outline="#00ff88", width=3
            )
            label_y = y1 - 14 if y1 > 30 else y2 + 14
            size_id[0] = canvas.create_text(
                (x1 + x2) // 2,
                label_y,
                text=f"{x2 - x1} × {y2 - y1} px",
                fill="#00ff88",
                font=("Arial", 12, "bold"),
            )

        def on_release(event: tk.Event) -> None:
            x1 = min(start_x, event.x)
            y1 = min(start_y, event.y)
            x2 = max(start_x, event.x)
            y2 = max(start_y, event.y)
            if x2 - x1 >= 10 and y2 - y1 >= 10:
                self.region = (x1, y1, x2, y2)
            overlay.destroy()

        def on_escape(event: tk.Event) -> None:
            overlay.destroy()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        overlay.bind("<Escape>", on_escape)

        overlay.wait_window()
        return self.region


def capture_region(region: Tuple[int, int, int, int]) -> Image.Image:
    """Grab a screen region as a PIL Image."""
    x1, y1, x2, y2 = region
    return ImageGrab.grab(bbox=(x1, y1, x2, y2))
