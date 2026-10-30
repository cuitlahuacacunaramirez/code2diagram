"""iso-diagram: architecture-as-YAML -> interactive isometric three.js diagram (HTML) + PNG."""
from .html import render_html
from .model import ModelError, load_file, load_text
from .scene import build_scene

__all__ = ["render_html", "build_scene", "load_file", "load_text", "ModelError", "render_file"]


def render_file(path, out_html=None):
    """Convenience: *.iso.yaml -> HTML string (and write it when out_html is given)."""
    model = load_file(path)
    html_text = render_html(build_scene(model))
    if out_html:
        from pathlib import Path
        p = Path(out_html)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html_text, encoding="utf-8")
    return html_text
