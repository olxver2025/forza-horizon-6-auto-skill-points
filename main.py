import sys
from threading import Event

import keyboard
import pyautogui

from process_manager import find_and_focus
from race_loop import run
from overlay import init_overlay, destroy_overlay, overlay_msg


BANNER = r"""
====================================
  Forza Horizon 6 Auto Race
  Press F8 at any time to stop
====================================
  Debug log: fh6auto_debug.log
  Screenshots: fh6auto_debug_raw_*.png
  Overlay may not render over fullscreen-exclusive games.
  Run FH6 in borderless/windowed mode for overlay support.
====================================
"""


def main() -> None:
    print(BANNER)

    init_overlay()

    try:
        find_and_focus()
    except RuntimeError as e:
        overlay_msg(f"ERROR: {e}", "error")
        print(f"[ERROR] {e}")
        print("Launch Forza Horizon 6 and try again.")
        destroy_overlay()
        sys.exit(1)

    overlay_msg("Game found and focused — starting loop", "state")
    print("[INFO] Game found and focused.")
    print("[INFO] Starting automation loop...")

    stop_flag = Event()
    keyboard.add_hotkey("f8", lambda: stop_flag.set())

    try:
        run(stop_flag)
    except KeyboardInterrupt:
        pass
    finally:
        for key in ("w", "a", "s", "d"):
            pyautogui.keyUp(key)
        overlay_msg("Stopped — keys released", "state")
        print("[INFO] Stopped.")
        destroy_overlay()


if __name__ == "__main__":
    main()
