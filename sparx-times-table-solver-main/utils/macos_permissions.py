"""macOS privacy permissions — check status and trigger system prompts."""
from __future__ import annotations

import ctypes
import ctypes.util
import logging
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PermissionStatus:
    screen_recording: bool
    accessibility: bool

    @property
    def all_granted(self) -> bool:
        return self.screen_recording and self.accessibility


def _coregraphics():
    path = ctypes.util.find_library("CoreGraphics")
    if not path:
        return None
    cg = ctypes.CDLL(path)
    if hasattr(cg, "CGPreflightScreenCaptureAccess"):
        cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
        cg.CGPreflightScreenCaptureAccess.argtypes = []
    if hasattr(cg, "CGRequestScreenCaptureAccess"):
        cg.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
        cg.CGRequestScreenCaptureAccess.argtypes = []
    return cg


def has_screen_recording() -> bool:
    cg = _coregraphics()
    if cg is not None and hasattr(cg, "CGPreflightScreenCaptureAccess"):
        try:
            return bool(cg.CGPreflightScreenCaptureAccess())
        except Exception as exc:
            logger.debug("CGPreflightScreenCaptureAccess failed: %s", exc)

    try:
        from PIL import ImageGrab

        shot = ImageGrab.grab(bbox=(0, 0, 2, 2))
        return shot is not None and shot.size[0] > 0
    except Exception as exc:
        logger.debug("Screen capture probe failed: %s", exc)
        return False


def request_screen_recording() -> bool:
    """Ask macOS for Screen Recording (shows system dialog on first request)."""
    cg = _coregraphics()
    if cg is not None and hasattr(cg, "CGRequestScreenCaptureAccess"):
        try:
            granted = bool(cg.CGRequestScreenCaptureAccess())
            logger.info("Screen Recording request result: %s", granted)
            if granted:
                return True
        except Exception as exc:
            logger.warning("CGRequestScreenCaptureAccess failed: %s", exc)

    try:
        from PIL import ImageGrab

        ImageGrab.grab(bbox=(0, 0, 4, 4))
    except Exception as exc:
        logger.warning("Screen capture activation grab failed: %s", exc)

    return has_screen_recording()


def has_accessibility() -> bool:
    try:
        import Quartz

        return bool(Quartz.AXIsProcessTrusted())
    except Exception as exc:
        logger.debug("Accessibility check failed: %s", exc)
        return False


def request_accessibility() -> bool:
    """Ask macOS for Accessibility (shows system dialog to open Settings)."""
    try:
        import Quartz

        options = {Quartz.kAXTrustedCheckOptionPrompt: True}
        granted = bool(Quartz.AXIsProcessTrustedWithOptions(options))
        logger.info("Accessibility request result: %s", granted)
        return granted
    except Exception as exc:
        logger.warning("Accessibility request failed: %s", exc)
        return has_accessibility()


def _open_settings_urls(urls: list[str]) -> None:
    for url in urls:
        try:
            subprocess.run(["open", url], check=False, timeout=5)
            return
        except Exception as exc:
            logger.debug("open %s failed: %s", url, exc)
    subprocess.run(
        ["open", "x-apple.systempreferences:com.apple.preference.security"],
        check=False,
    )


def open_screen_recording_settings() -> None:
    _open_settings_urls(
        [
            "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_ScreenCapture",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
        ]
    )


def open_accessibility_settings() -> None:
    _open_settings_urls(
        [
            "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_Accessibility",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        ]
    )


def get_status() -> PermissionStatus:
    return PermissionStatus(
        screen_recording=has_screen_recording(),
        accessibility=has_accessibility(),
    )


def request_all() -> PermissionStatus:
    """Trigger macOS permission prompts, then return current status."""
    if sys.platform != "darwin":
        return PermissionStatus(True, True)

    request_screen_recording()
    request_accessibility()
    return get_status()
