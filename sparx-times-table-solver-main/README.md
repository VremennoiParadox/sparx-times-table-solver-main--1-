# Sparx Solver Pro

A desktop app that reads maths questions from your screen (OCR), solves them, and types the answers into Sparx.

## What It Does

- Lets you drag-select the question area on screen.
- Reads the question with EasyOCR.
- Solves the question with sympy.
- Types the answer and presses Enter.
- If it reaches a "next" screen it presses Enter.
- Runs for the number of rounds you choose (25 is a good default).
- Safe stop: move mouse to the top-left corner `(0,0)`.

---

## macOS — use without Python (recommended)

Build the app **once** on your Mac, then run it like any other application from **Applications**. You do not need Python installed to use it day to day.

### Daily use (after the app is built)

1. Open **Sparx Solver Pro** from Applications (double-click).
2. **First time only:** If macOS blocks the app, **right-click** it → **Open** → confirm. This is normal for unsigned personal apps.
3. On first launch, the app **asks macOS for permissions** (Screen Recording and Accessibility popups). Use the in-app buttons if you need to open Settings manually. Turn both **on** for **Sparx Solver Pro**, then **quit (Cmd+Q) and reopen**.
4. In the app: **Select Region** → drag around the question → set **Rounds** → **Start** → switch to your Sparx window.

**First launch** may take 10–30 seconds while OCR loads inside the bundle. Later launches are faster.

Logs (if something goes wrong): `~/Library/Logs/Sparx Solver Pro/app.log`

### Build the `.app` once (on your Mac)

You need Python only for this one-time build step.

1. Copy this project to your Mac (git, USB, AirDrop, etc.).
2. Open **Terminal**, go to the project folder, and run:

```bash
bash scripts/build_mac.sh
```

3. When it finishes, drag **`dist/Sparx Solver Pro.app`** into **Applications**.

The `.app` is large (~800MB–1.5GB) because it includes Python, PyTorch, and OCR models. That is expected.

**Note:** The `.app` cannot be built on Windows. Build on the same Mac you will use it on (Apple Silicon or Intel).

---

## Run from source (developers)

### Requirements

- Python 3.10+
- Dependencies in `requirements.txt`

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### macOS permissions (when running from Terminal)

Give your **terminal** app (Terminal, iTerm, etc.):

- **Screen Recording**
- **Accessibility**

Path: **System Settings → Privacy & Security**

When using the bundled `.app`, grant permissions to **Sparx Solver Pro**, not Terminal.

### SSL / EasyOCR model download (source only)

If you see `CERTIFICATE_VERIFY_FAILED` when running from source:

```bash
python3 -m pip install --upgrade pip certifi
open "/Applications/Python 3.x/Install Certificates.command"
```

Bundled builds download models during `build_mac.sh`, so end users usually avoid this.

---

## How To Use

1. Click **Select Region** and drag over the question area.
2. Enter **Rounds** (25 recommended).
3. Click **Start**.
4. Quickly switch to your Sparx window.

Hotkeys: **Ctrl+Enter** Start · **Space** Pause/Resume · **Esc** Stop

## Stop

- Click **Stop**, press **Esc**, or move the mouse to the top-left corner `(0,0)`.

## Troubleshooting

### It does not type answers

- Make sure the answer input box is focused in Sparx.
- On macOS: check **Accessibility** is enabled for **Sparx Solver Pro** (or your terminal if running from source).

### Screen capture is black or empty

- On macOS: open the app and use **Request permissions again** in the permissions window, or enable **Screen Recording** for **Sparx Solver Pro** in System Settings, then quit and reopen the app.

### Gatekeeper will not open the app

- Right-click **Sparx Solver Pro** → **Open** → **Open** again.

### The `.app` opens then closes instantly

1. Copy the **updated** project from your PC to the Mac (the fix renames `packaging/` → `bundle/` to avoid a Python crash).
2. Rebuild: `bash scripts/build_mac.sh`
3. Replace the old app in Applications with the new one from `dist/`.
4. If it still closes, open this file in TextEdit and send the last lines for help:
   - `~/Library/Logs/Sparx Solver Pro/crash.log`
5. Or run from Terminal to see the error live:
   ```bash
   "/Applications/Sparx Solver Pro.app/Contents/MacOS/Sparx Solver Pro"
   ```
