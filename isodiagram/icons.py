"""Icon lookup: '<pack>:<id>' -> data URI + pixel aspect, from assets/icons."""
from __future__ import annotations

import base64
import re
from pathlib import Path

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"

_num = r"([0-9.]+)"


def _size(svg: str) -> tuple[float, float]:
    head = re.search(r"<svg\b[^>]*>", svg, re.S)
    tag = head.group(0) if head else ""
    w = re.search(r'\swidth="' + _num, tag)
    h = re.search(r'\sheight="' + _num, tag)
    if w and h:
        return float(w.group(1)), float(h.group(1))
    vb = re.search(r'viewBox="\s*[-0-9.]+[ ,]+[-0-9.]+[ ,]+' + _num + r"[ ,]+" + _num, tag)
    if vb:
        return float(vb.group(1)), float(vb.group(2))
    return 64.0, 64.0


def _ensure_size(svg: str, w: float, h: float) -> str:
    """Give the root <svg> explicit width/height so every browser rasterises it at a sane size."""
    m = re.search(r"<svg\b[^>]*>", svg, re.S)
    if not m or re.search(r'\swidth="', m.group(0)):
        return svg
    return svg[: m.end() - 1] + f' width="{w:g}" height="{h:g}"' + svg[m.end() - 1:]


def load_icon(key: str) -> dict | None:
    if ":" not in key:
        key = f"isoflow:{key}"
    pack, _, icon_id = key.partition(":")
    path = ICON_DIR / pack / f"{icon_id}.svg"
    if not path.is_file():
        return None
    svg = path.read_text(encoding="utf-8", errors="replace")
    w, h = _size(svg)
    svg = _ensure_size(svg, w, h)
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return {"uri": uri, "w": w, "h": h}
