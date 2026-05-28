import ctypes

import psutil
import win32gui
import win32con
import win32process

from overlay import overlay_msg, logger

FORZA_PROCESS = "forzahorizon6.exe"


def _enum_windows_callback(hwnd: int, result: list) -> bool:
    if not win32gui.IsWindowVisible(hwnd):
        return True
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        proc = psutil.Process(pid)
        if proc.name().lower() == FORZA_PROCESS:
            result.append(hwnd)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return True


def _is_forza_running() -> bool:
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == FORZA_PROCESS:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def _get_forza_hwnd() -> int:
    results: list = []
    win32gui.EnumWindows(_enum_windows_callback, results)
    if not results:
        raise RuntimeError(f"Window for {FORZA_PROCESS} not found")
    return results[0]


_cached_hwnd: int | None = None

def find_and_focus() -> None:
    global _cached_hwnd
    if not _is_forza_running():
        raise RuntimeError(f"{FORZA_PROCESS} is not running")

    hwnd = _get_forza_hwnd()
    _cached_hwnd = hwnd
    title = win32gui.GetWindowText(hwnd)
    logger.info("Found HWND=0x%X title=%r", hwnd, title)
    overlay_msg(f"Found: {title} (0x{hwnd:X})", "state")

    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    ctypes.windll.user32.SetForegroundWindow(hwnd)
    ctypes.windll.user32.SetFocus(hwnd)
    overlay_msg("Window focused", "state")

def get_forza_hwnd() -> int | None:
    return _cached_hwnd
