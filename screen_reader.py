import time
from typing import Optional

import ctypes
import mss
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

from overlay import overlay_msg, logger

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_debug_index = 0

_OCR_CONFIG = "--psm 11 --oem 3"
_OCR_CONF_THRESHOLD = 40


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


def _preprocess(image: Image.Image) -> Image.Image:
    grey = image.convert("L")
    # Upscale 2x — tesseract accuracy improves significantly on larger text
    w, h = grey.size
    grey = grey.resize((w * 2, h * 2), Image.LANCZOS)
    enhanced = ImageEnhance.Contrast(grey).enhance(3.0)
    return enhanced.filter(ImageFilter.SHARPEN)


def find_text(image: Image.Image, query: str, region: tuple[int, int, int, int] | None = None) -> bool:
    global _debug_index
    full_image = image  # keep reference to full capture for debug
    if region is not None:
        try:
            image = image.crop(region)
        except Exception as exc:
            logger.debug("Region crop failed: %s", exc)

    processed = _preprocess(image)

    try:
        data = pytesseract.image_to_data(
            processed, config=_OCR_CONFIG, output_type=pytesseract.Output.DICT
        )
        words = [
            data["text"][i]
            for i in range(len(data["text"]))
            if data["text"][i].strip() and int(data["conf"][i]) >= _OCR_CONF_THRESHOLD
        ]
        text = " ".join(words)
    except Exception as exc:
        logger.debug("OCR exception: %s", exc)
        return False

    found = query.lower() in text.lower()

    if found:
        overlay_msg(f'OCR MATCH: "{query}" found', "match")
    else:
        short = text[:120].replace("\n", " / ")
        overlay_msg(f'OCR miss: wanted="{query}" got="{short}"', "ocr")
        _debug_save(processed, "_proc", _debug_index)
        _debug_save(image, "_raw", _debug_index)
        _debug_save(full_image, "_full", _debug_index)
        _debug_index = (_debug_index + 1) % 30

    return found


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
            lf, tf, rf, bf = region_frac
            region = (
                int(img.width * lf),
                int(img.height * tf),
                int(img.width * rf),
                int(img.height * bf),
            )
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
        for query in queries:
            if find_text(img, query):
                return query
        if timeout is not None and (time.monotonic() - start) >= timeout:
            logger.debug("wait_for_any_text TIMEOUT for: %s", queries)
            overlay_msg(f"TIMEOUT waiting for any of: {queries}", "warn")
            return None
        time.sleep(interval)
