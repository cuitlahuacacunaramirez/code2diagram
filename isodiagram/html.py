"""Assemble the self-contained interactive HTML (three.js + viewer + scene JSON, no network needed)."""
from __future__ import annotations

import base64
import html
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "assets" / "vendor"
VIEWER = ROOT / "viewer"


@lru_cache(maxsize=None)
def _data_uri(path: Path) -> str:
    return "data:text/javascript;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _importmap() -> str:
    three, orbit = VENDOR / "three.module.js", VENDOR / "OrbitControls.js"
    if not three.is_file() or not orbit.is_file():
        raise FileNotFoundError("three.js is missing - run: python tools/fetch_assets.py (or start.ps1)")
    return json.dumps({"imports": {"three": _data_uri(three), "orbit": _data_uri(orbit)}})


def render_html(scene: dict) -> str:
    template = (VIEWER / "template.html").read_text(encoding="utf-8")
    viewer_js = (VIEWER / "viewer.js").read_text(encoding="utf-8")
    scene_json = json.dumps(scene, separators=(",", ":")).replace("</", "<\\/")
    values = {
        "TITLE": html.escape(scene.get("title") or "Diagram"),
        "IMPORTMAP": _importmap(),
        "SCENE": scene_json,
        "VIEWER": viewer_js.replace("</script", "<\\/script"),
    }
    return re.sub(r"__(TITLE|IMPORTMAP|SCENE|VIEWER)__", lambda m: values[m.group(1)], template)
