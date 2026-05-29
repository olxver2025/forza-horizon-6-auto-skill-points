import time

import pyautogui

from overlay import overlay_msg, logger

pyautogui.FAILSAFE = False

DELAY_MULTIPLIER = 1.25


def _d(seconds: float) -> float:
    return seconds * DELAY_MULTIPLIER


def tap(key: str, presses: int = 1, delay: float = 0.1) -> None:
    scaled_delay = _d(delay)
    for i in range(presses):
        pyautogui.press(key)
        if presses == 1:
            overlay_msg(f"TAP: {key}", "action")
        else:
            overlay_msg(f"TAP: {key} ({i + 1}/{presses})", "action")
        time.sleep(scaled_delay)
    logger.debug("tap: %s x%d", key, presses)


def hold_until_text(key: str, text: str, check_interval: float = 0.3, start_delay: float = 0.0) -> None:
    from screen_reader import capture_screen, find_text

    scaled_interval = _d(check_interval)
    scaled_delay = _d(start_delay)
    overlay_msg(f'HOLD: "{key}" until "{text}" (delay={start_delay:.0f}s)', "action")
    logger.debug("hold_until_text: key=%s text=%s start_delay=%.1f", key, text, start_delay)
    pyautogui.keyDown(key)
    try:
        if scaled_delay > 0:
            time.sleep(scaled_delay)
        while True:
            img = capture_screen()
            if find_text(img, text, save_debug=False):
                overlay_msg(f'HOLD released: found "{text}"', "match")
                break
            time.sleep(scaled_interval)
    finally:
        pyautogui.keyUp(key)


def type_text(text: str, interval: float = 0.05) -> None:
    scaled_interval = _d(interval)
    overlay_msg(f'TYPE: "{text}"', "action")
    pyautogui.typewrite(text, interval=scaled_interval)
    logger.debug("type_text: %s", text)


def sleep(seconds: float) -> None:
    scaled = _d(seconds)
    logger.debug("sleep: %.1fs (raw=%.1fs)", scaled, seconds)
    time.sleep(scaled)
