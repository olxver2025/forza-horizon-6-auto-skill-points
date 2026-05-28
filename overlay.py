import logging
import sys
import tkinter as tk
from datetime import datetime

logger = logging.getLogger("fh6auto")
logger.setLevel(logging.DEBUG)

_file_handler = logging.FileHandler("fh6auto_debug.log", encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
_file_handler.setFormatter(_file_formatter)
logger.addHandler(_file_handler)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(logging.INFO)
_console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
_console_handler.setFormatter(_console_formatter)
logger.addHandler(_console_handler)


_overlay_root: tk.Tk | None = None
_overlay_text: tk.Text | None = None
_overlay_stats_label: tk.Label | None = None
_overlay_lines: list[tuple[str, str]] = []
MAX_OVERLAY_LINES = 16
_started = False


def _overlay_init() -> None:
    global _overlay_root, _overlay_text, _overlay_stats_label, _started

    _overlay_root = tk.Tk()
    _overlay_root.title("FH6 Debug")
    _overlay_root.geometry("440x360+10+10")
    _overlay_root.configure(bg="#111111")
    _overlay_root.attributes("-topmost", True)
    _overlay_root.attributes("-alpha", 0.88)
    _overlay_root.overrideredirect(True)
    _overlay_root.deiconify()
    _overlay_root.lift()

    _overlay_stats_label = tk.Label(
        _overlay_root,
        text="Races: 0  |  Skill pts: 0  |  Time: 00:00:00",
        bg="#1a1a2e",
        fg="#ffd700",
        font=("Consolas", 10, "bold"),
        anchor="w",
        padx=6,
        pady=3,
    )
    _overlay_stats_label.pack(fill=tk.X)

    _overlay_text = tk.Text(
        _overlay_root,
        bg="#111111",
        fg="#00ff00",
        font=("Consolas", 9),
        wrap=tk.WORD,
        borderwidth=0,
        highlightthickness=0,
        relief="flat",
        padx=6,
        pady=4,
        state=tk.DISABLED,
        cursor="none",
    )
    _overlay_text.pack(fill=tk.BOTH, expand=True)

    _overlay_text.tag_configure("state", foreground="#00ffff")
    _overlay_text.tag_configure("warn", foreground="#ffaa00")
    _overlay_text.tag_configure("error", foreground="#ff4444")
    _overlay_text.tag_configure("match", foreground="#44ff44")
    _overlay_text.tag_configure("action", foreground="#aaaaaa")
    _overlay_text.tag_configure("ocr", foreground="#8888ff")

    _started = True


def _overlay_pump() -> None:
    if _overlay_root is None:
        return
    try:
        _overlay_root.deiconify()
        _overlay_root.lift()
        _overlay_root.update()
    except tk.TclError:
        pass


def _overlay_append(text: str, tag: str = "") -> None:
    global _overlay_lines, _overlay_text
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {text}"
    _overlay_lines.append((line, tag))

    if len(_overlay_lines) > MAX_OVERLAY_LINES:
        _overlay_lines = _overlay_lines[-MAX_OVERLAY_LINES:]

    if _overlay_text is None:
        return

    try:
        _overlay_text.configure(state=tk.NORMAL)
        _overlay_text.delete("1.0", tk.END)
        for ln, tg in _overlay_lines:
            _overlay_text.insert(tk.END, ln + "\n", tg if tg else None)
        _overlay_text.configure(state=tk.DISABLED)
        _overlay_text.see(tk.END)
    except tk.TclError:
        pass


def overlay_msg(text: str, tag: str = "") -> None:
    logger.debug("%s", text)
    if _started:
        _overlay_append(text, tag)
        _overlay_pump()


def init_overlay() -> None:
    _overlay_init()
    _overlay_append("FH6 Auto Race - debug overlay", "state")
    _overlay_pump()


def overlay_stats(races: int, elapsed_seconds: float) -> None:
    if _overlay_stats_label is None:
        return
    skill_pts = races * 10
    h = int(elapsed_seconds // 3600)
    m = int((elapsed_seconds % 3600) // 60)
    s = int(elapsed_seconds % 60)
    text = f"Races: {races}  |  Skill pts: {skill_pts}  |  Time: {h:02d}:{m:02d}:{s:02d}"
    try:
        _overlay_stats_label.configure(text=text)
        _overlay_pump()
    except tk.TclError:
        pass


def destroy_overlay() -> None:
    global _overlay_root, _overlay_text, _overlay_stats_label, _started
    _started = False
    if _overlay_root is not None:
        try:
            _overlay_root.destroy()
        except tk.TclError:
            pass
        _overlay_root = None
        _overlay_text = None
        _overlay_stats_label = None
    _overlay_lines.clear()


def overlay_state(state: str) -> None:
    overlay_msg(f"STATE: {state}", "state")
