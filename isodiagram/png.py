"""PNG export by screenshotting the HTML in a headless Edge/Chrome (WebGL via SwiftShader, no GPU needed)."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_browser() -> str:
    env = os.environ.get("ISO_BROWSER")
    if env and Path(env).is_file():
        return env
    for c in CANDIDATES:
        if Path(c).is_file():
            return c
    for name in ("msedge", "chrome", "chromium", "google-chrome"):
        p = shutil.which(name)
        if p:
            return p
    raise FileNotFoundError("No Edge/Chrome found. Install one or set ISO_BROWSER to its executable path.")


def html_to_png(html_path: str | Path, png_path: str | Path, width: int = 1920, height: int = 1080,
                scale: float = 1.0, timeout: int = 120) -> Path:
    html_path, png_path = Path(html_path).resolve(), Path(png_path).resolve()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    if png_path.exists():
        png_path.unlink()
    with tempfile.TemporaryDirectory(prefix="c2d-browser-") as profile:
        cmd = [
            find_browser(), "--headless=new", "--no-first-run", "--no-default-browser-check",
            f"--user-data-dir={profile}", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
            "--ignore-gpu-blocklist", "--hide-scrollbars", "--allow-file-access-from-files",
            f"--force-device-scale-factor={scale}", f"--window-size={width},{height}",
            "--virtual-time-budget=15000", f"--screenshot={png_path}",
            html_path.as_uri() + "#clean",
        ]
        try:
            subprocess.run(cmd, check=False, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            pass  # the screenshot may still have been written
    if not png_path.is_file() or png_path.stat().st_size == 0:
        raise RuntimeError("Headless browser did not produce a screenshot (try opening the HTML and using 'Export PNG').")
    return png_path
