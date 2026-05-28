from enum import Enum, auto
from threading import Event

import time as _time

from process_manager import find_and_focus
from screen_reader import wait_for_text, wait_for_any_text, find_text, capture_screen
from input_handler import tap, hold_until_text, type_text, sleep
from overlay import overlay_state, overlay_msg, overlay_stats, logger


class State(Enum):
    INIT = auto()
    CHECK_MENU = auto()
    NAVIGATE_TO_EVENT = auto()
    WAIT_FOR_START = auto()
    RACING = auto()
    POST_RACE = auto()
    WAIT_FOR_RESTART = auto()


FIRST_RUN = True
_races_completed = 0
_session_start: float | None = None


_MENU_ANCHORS = ["campaign", "cars", "my horizon", "online", "creative hub", "store"]

_RACE_READY_ANCHORS = [
    "start race event",
    "difficulty & settings",
    "tune car",
    "starting grid",
    "quit race",
]


def _check_menu(stop_flag: Event) -> None:
    overlay_msg("Waiting 3s before menu checks...", "action")
    sleep(3.0)
    for attempt in range(1, 6):
        if stop_flag.is_set():
            return
        overlay_msg(f"Menu check {attempt}/5", "action")
        img = capture_screen()
        for anchor in _MENU_ANCHORS:
            if find_text(img, anchor):
                overlay_msg(f"Found menu anchor: {anchor!r}", "match")
                return
        logger.debug("escape attempt %d — no menu anchor found", attempt)
        if attempt > 1:
            overlay_msg(f"Pressing ESC (attempt {attempt})", "warn")
            tap("escape")
        else:
            overlay_msg(f"Waiting before ESC (attempt {attempt})", "warn")
        sleep(1.5)
    overlay_msg("Menu check FAILED after 5 attempts", "error")


def _navigate_to_event(stop_flag: Event) -> None:
    overlay_state("NAVIGATE_TO_EVENT")
    tap("pagedown", presses=4, delay=0.3)
    tap("enter")
    sleep(0.55)
    tap("enter")
    sleep(0.55)
    tap("backspace")
    sleep(0.33)
    tap("up")
    sleep(0.33)
    tap("enter")
    sleep(0.55)
    type_text("890169683")
    sleep(0.33)
    tap("enter")
    sleep(1.65)
    tap("down")
    sleep(0.33)
    tap("enter")
    sleep(3.3)
    tap("enter")
    sleep(1.65)
    tap("enter")
    sleep(1.65)
    tap("enter")
    sleep(1.65)


def _wait_for_start(stop_flag: Event) -> bool:
    overlay_state("WAIT_FOR_START")
    matched = wait_for_any_text(_RACE_READY_ANCHORS, timeout=120)
    return matched is not None


def _racing(stop_flag: Event) -> None:
    global _session_start
    overlay_state("RACING")
    if _session_start is None:
        _session_start = _time.monotonic()
    hold_until_text("w", "finished", check_interval=0.1, start_delay=20.0)


def _post_race(stop_flag: Event) -> None:
    global _races_completed
    _races_completed += 1
    elapsed = _time.monotonic() - _session_start if _session_start else 0.0
    overlay_stats(_races_completed, elapsed)
    overlay_msg(f"Race {_races_completed} complete — {_races_completed * 10} skill pts", "match")
    overlay_state("POST_RACE")
    sleep(2.0)
    overlay_msg("Delaying before pressing X", "action")
    sleep(4.0)
    tap("x")
    sleep(0.5)
    tap("enter")
    sleep(0.5)


def _wait_for_restart(stop_flag: Event) -> bool:
    overlay_state("WAIT_FOR_RESTART")
    matched = wait_for_any_text(_RACE_READY_ANCHORS, timeout=120)
    return matched is not None


def run(stop_flag: Event) -> None:
    global FIRST_RUN
    state = State.INIT

    while not stop_flag.is_set():
        if state == State.INIT:
            overlay_state("INIT")
            find_and_focus()
            sleep(2.0)
            state = State.CHECK_MENU

        elif state == State.CHECK_MENU:
            overlay_state("CHECK_MENU")
            _check_menu(stop_flag)
            if stop_flag.is_set():
                return
            state = State.NAVIGATE_TO_EVENT

        elif state == State.NAVIGATE_TO_EVENT:
            if FIRST_RUN:
                _navigate_to_event(stop_flag)
                FIRST_RUN = False
            if stop_flag.is_set():
                return
            state = State.WAIT_FOR_START

        elif state == State.WAIT_FOR_START:
            if _wait_for_start(stop_flag):
                tap("enter")
                sleep(0.5)
                state = State.RACING
            else:
                overlay_msg("Start not found — going back to menu check", "warn")
                state = State.CHECK_MENU

        elif state == State.RACING:
            _racing(stop_flag)
            if stop_flag.is_set():
                return
            state = State.POST_RACE

        elif state == State.POST_RACE:
            _post_race(stop_flag)
            if stop_flag.is_set():
                return
            state = State.WAIT_FOR_RESTART

        elif state == State.WAIT_FOR_RESTART:
            if _wait_for_restart(stop_flag):
                tap("enter")
                sleep(0.5)
                state = State.RACING
            else:
                overlay_msg("Restart not found — going back to menu check", "warn")
                state = State.CHECK_MENU
