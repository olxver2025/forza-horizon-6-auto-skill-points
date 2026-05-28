# forza horizon 6 auto skill points

automatically farms skill points by repeatedly running a shared route event.

---

## requirements

- windows 10/11
- forza horizon 6 running in borderless windowed mode
- python 3.11+
- tesseract ocr

---

## setup

**1. install tesseract**

download and run the installer from https://github.com/UB-Mannheim/tesseract/wiki

install it to the default path: `c:\program files\tesseract-ocr\`

make sure english language data is included.

**2. install python dependencies**

```
pip install -r requirements.txt
```

**3. configure the game**

- run forza horizon 6 in borderless windowed mode
- make sure you are on the main menu before starting the script

---

## usage

```
python main.py
```

the script will:
1. find and focus the forza horizon 6 window
2. navigate to the shared event using code `890169683`
3. start the race, hold w until finished, then repeat
4. press `f8` at any time to stop

an overlay will appear in the top-left corner of the screen showing the current state, race count, skill points earned, and session time.

---

## notes

- the script expects to start from the main menu
- if it loses its place it will press esc and try to return to the main menu automatically
- debug screenshots are saved as `fh6auto_debug_*.png` in the script folder if ocr fails
- logs are written to `fh6auto_debug.log`
