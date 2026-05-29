import time
from typing import Optional
import re
from difflib import SequenceMatcher

import ctypes
import mss
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

from overlay import overlay_msg, logger

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_debug_index = 0

_UPSCALE = 2

_OCR_CONFIG = "--psm 11 --oem 3"
_OCR_CONFIG_BLOCK = "--psm 6 --oem 3"
_OCR_CONFIGS = (_OCR_CONFIG, _OCR_CONFIG_BLOCK)
_OCR_CONF_THRESHOLD = 40

_FINISHED_REGION_FRACS = (
    (0.20, 0.00, 0.80, 0.38),
    (0.18, 0.22, 0.82, 0.68),
    (0.00, 0.00, 1.00, 0.82),
)


def _conf_value(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return -1


def _normalise_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _text_matches(query: str, text: str, fuzzy_threshold: float = 0.84) -> bool:
    q = _normalise_text(query)
    t = _normalise_text(text)
    if not q or not t:
        return False
    if q in t:
        return True
    if len(q) <= 4:
        return False

    q_tokens = q.split()
    t_tokens = t.split()
    window = max(1, len(q_tokens))
    candidates = []
    for size in (window, window + 1):
        if size > len(t_tokens):
            continue
        for start in range(0, len(t_tokens) - size + 1):
            candidates.append(" ".join(t_tokens[start:start + size]))

    for candidate in candidates:
        if SequenceMatcher(None, q, candidate).ratio() >= fuzzy_threshold:
            return True

    if len(q_tokens) > 1:
        clipped_first = q_tokens[0][1:] if len(q_tokens[0]) > 3 else q_tokens[0]
        clipped_query = " ".join([clipped_first] + q_tokens[1:])
        if clipped_query in t:
            return True
        for candidate in candidates:
            if SequenceMatcher(None, clipped_query, candidate).ratio() >= 0.88:
                return True
    return False


def capture_screen() -> Image.Image:
    """Capture FH6 client area only, bypassing the overlay via PrintWindow."""
    try:
        from process_manager import get_forza_hwnd
        import win32gui
        import win32ui

        hwnd = get_forza_hwnd()
        if hwnd:
            cr = win32gui.GetClientRect(hwnd)
            width, height = cr[2], cr[3]
            if width > 0 and height > 0:
                hwndDC = win32gui.GetWindowDC(hwnd)
                mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                saveDC = mfcDC.CreateCompatibleDC()
                bmp = win32ui.CreateBitmap()
                bmp.CreateCompatibleBitmap(mfcDC, width, height)
                saveDC.SelectObject(bmp)
                # PW_CLIENTONLY=0x1, PW_RENDERFULLCONTENT=0x2 (forces DirectX blit)
                ok = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 0x3)
                bmpstr = bmp.GetBitmapBits(True)
                win32gui.DeleteObject(bmp.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwndDC)
                if ok:
                    return Image.frombuffer("RGB", (width, height), bmpstr, "raw", "BGRX", 0, 1)
    except Exception as e:
        logger.debug("PrintWindow capture failed, falling back to mss: %s", e)

    # Fallback: mss screen grab of the FH6 client rect
    try:
        from process_manager import get_forza_hwnd
        import win32gui

        hwnd = get_forza_hwnd()
        if hwnd:
            client_left, client_top = win32gui.ClientToScreen(hwnd, (0, 0))
            cr = win32gui.GetClientRect(hwnd)
            monitor = {"left": client_left, "top": client_top, "width": cr[2], "height": cr[3]}
            with mss.mss() as sct:
                raw = sct.grab(monitor)
                return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    except Exception as e:
        logger.debug("mss window capture failed, falling back to primary monitor: %s", e)

    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def _preprocess(image: Image.Image, contrast: float = 3.0) -> Image.Image:
    grey = image.convert("L")
    # Upscale 2x — tesseract accuracy improves significantly on larger text
    w, h = grey.size
    grey = grey.resize((w * _UPSCALE, h * _UPSCALE), Image.LANCZOS)
    enhanced = ImageEnhance.Contrast(grey).enhance(contrast)
    return enhanced.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))


def _ocr_words(image: Image.Image, conf_threshold: int) -> list[str]:
    words: list[str] = []
    seen: set[tuple[str, int, int]] = set()
    for config in _OCR_CONFIGS:
        try:
            data = pytesseract.image_to_data(
                image, config=config, output_type=pytesseract.Output.DICT
            )
            for i in range(len(data["text"])):
                word = data["text"][i].strip()
                if not word or _conf_value(data["conf"][i]) < conf_threshold:
                    continue
                key = (_normalise_text(word), data["left"][i] // 20, data["top"][i] // 20)
                if key in seen:
                    continue
                seen.add(key)
                words.append(word)
        except Exception as exc:
            logger.debug("_ocr_words exc with %s: %s", config, exc)
    return words


def _read_ocr_text(image: Image.Image) -> tuple[str, Image.Image]:
    processed = _preprocess(image)
    words = _ocr_words(processed, _OCR_CONF_THRESHOLD)

    if not words:
        softer = _preprocess(image, contrast=1.8)
        words = _ocr_words(softer, max(_OCR_CONF_THRESHOLD - 15, 10))
        if words:
            processed = softer

    return " ".join(words), processed


def _region_from_frac(
    image: Image.Image,
    region_frac: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    lf, tf, rf, bf = region_frac
    return (
        int(image.width * lf),
        int(image.height * tf),
        int(image.width * rf),
        int(image.height * bf),
    )


def _find_finished_text(image: Image.Image) -> bool:
    for region_frac in _FINISHED_REGION_FRACS:
        region = _region_from_frac(image, region_frac)
        crop = image.crop(region)
        text, _processed = _read_ocr_text(crop)
        if _text_matches("finished", text, fuzzy_threshold=0.80):
            overlay_msg('OCR MATCH: "finished" found', "match")
            return True
    overlay_msg('OCR miss: wanted="finished"', "ocr")
    return False


def find_text(
    image: Image.Image,
    query: str,
    region: tuple[int, int, int, int] | None = None,
    save_debug: bool = True,
) -> bool:
    global _debug_index
    full_image = image  # keep reference to full capture for debug

    if region is None and _normalise_text(query) == "finished":
        return _find_finished_text(image)

    if region is not None:
        try:
            image = image.crop(region)
        except Exception as exc:
            logger.debug("Region crop failed: %s", exc)

    text, processed = _read_ocr_text(image)
    found = _text_matches(query, text)

    if found:
        overlay_msg(f'OCR MATCH: "{query}" found', "match")
    else:
        short = text[:120].replace("\n", " / ")
        overlay_msg(f'OCR miss: wanted="{query}" got="{short}"', "ocr")
        if save_debug:
            _debug_save(processed, "_proc", _debug_index)
            _debug_save(image, "_raw", _debug_index)
            _debug_save(full_image, "_full", _debug_index)
            _debug_index = (_debug_index + 1) % 30

    return found


def find_any_text(
    image: Image.Image,
    queries: list[str],
    region: tuple[int, int, int, int] | None = None,
) -> Optional[str]:
    global _debug_index
    full_image = image
    if region is not None:
        try:
            image = image.crop(region)
        except Exception as exc:
            logger.debug("Region crop failed: %s", exc)

    text, processed = _read_ocr_text(image)
    for query in queries:
        if _text_matches(query, text):
            overlay_msg(f'OCR MATCH (any): "{query}" found', "match")
            return query

    short = text[:120].replace("\n", " / ")
    overlay_msg(f'OCR miss (any of {len(queries)}): got="{short}"', "ocr")
    _debug_save(processed, "_proc", _debug_index)
    _debug_save(image, "_raw", _debug_index)
    _debug_save(full_image, "_full", _debug_index)
    _debug_index = (_debug_index + 1) % 30
    return None


def _debug_save(img: Image.Image, suffix: str, idx: int) -> None:
    try:
        img.save(f"fh6auto_debug{suffix}_{idx:03d}.png")
    except Exception:
        pass


def wait_for_text(
    query: str,
    timeout: Optional[float] = None,
    interval: float = 0.5,
    region_frac: tuple[float, float, float, float] | None = None,
) -> bool:
    """
    region_frac: (left, top, right, bottom) as fractions of image dimensions, e.g. (0.0, 0.6, 1.0, 1.0)
    """
    start = time.monotonic()
    while True:
        img = capture_screen()
        region = None
        if region_frac is not None:
            region = _region_from_frac(img, region_frac)
        if find_text(img, query, region=region):
            return True
        if timeout is not None and (time.monotonic() - start) >= timeout:
            logger.debug("wait_for_text TIMEOUT for: %s", query)
            overlay_msg(f'TIMEOUT waiting for "{query}"', "warn")
            return False
        time.sleep(interval)


def wait_for_any_text(
    queries: list[str],
    timeout: Optional[float] = None,
    interval: float = 0.5,
) -> Optional[str]:
    """Returns the matched query string, or None on timeout."""
    start = time.monotonic()
    while True:
        img = capture_screen()
        matched = find_any_text(img, queries)
        if matched is not None:
            return matched
        if timeout is not None and (time.monotonic() - start) >= timeout:
            logger.debug("wait_for_any_text TIMEOUT for: %s", queries)
            overlay_msg(f"TIMEOUT waiting for any of: {queries}", "warn")
            return None
        time.sleep(interval)
