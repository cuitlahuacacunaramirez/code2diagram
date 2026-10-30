"""Tiny local web service: lists *.iso.yaml files and renders them on demand (edit YAML, refresh the browser)."""
from __future__ import annotations

import html as htmllib
import tempfile
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import render_html, build_scene, load_file, ModelError
from .png import html_to_png

ROOT = Path(__file__).resolve().parent.parent


def _files(dirs: list[Path]) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for d in dirs:
        for p in sorted(d.glob("*.iso.yaml")) + sorted(d.glob("*.iso.yml")):
            found.setdefault(p.name, p)
    return found


def make_handler(dirs: list[Path]):
    class Handler(BaseHTTPRequestHandler):
        server_version = "iso-diagram/1"

        def log_message(self, fmt, *args):  # quieter console
            print("[serve]", fmt % args, flush=True)

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _page(self, code: int, title: str, body: str):
            page = (f"<!doctype html><meta charset=utf-8><title>{htmllib.escape(title)}</title>"
                    "<style>body{font:15px/1.5 'Segoe UI',sans-serif;max-width:760px;margin:40px auto;padding:0 16px;color:#0f172a}"
                    "a{color:#2563eb}li{margin:6px 0}code,pre{background:#f1f5f9;padding:2px 6px;border-radius:4px}"
                    "pre{padding:12px;white-space:pre-wrap}</style>" + body)
            self._send(code, page.encode("utf-8"), "text/html; charset=utf-8")

        def do_GET(self):
            path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
            files = _files(dirs)
            if path == "/":
                items = "".join(
                    f"<li><b>{htmllib.escape(n)}</b> &mdash; <a href='/view/{urllib.parse.quote(n)}'>interactive</a> · "
                    f"<a href='/png/{urllib.parse.quote(n)}'>PNG</a> · <a href='/src/{urllib.parse.quote(n)}'>source</a></li>"
                    for n in files) or "<li>No *.iso.yaml files found.</li>"
                return self._page(200, "iso-diagram", f"<h1>iso-diagram</h1><ul>{items}</ul>"
                                  f"<p>Served from: {', '.join(htmllib.escape(str(d)) for d in dirs)}</p>")
            kind, _, name = path.lstrip("/").partition("/")
            if kind in ("view", "png", "src") and name in files:
                src = files[name]
                if kind == "src":
                    return self._send(200, src.read_bytes(), "text/plain; charset=utf-8")
                try:
                    html_text = render_html(build_scene(load_file(src)))
                except ModelError as e:
                    lis = "".join(f"<li>{htmllib.escape(m)}</li>" for m in e.errors)
                    return self._page(400, "Invalid diagram", f"<h1>{htmllib.escape(name)} is not valid</h1><ul>{lis}</ul>")
                if kind == "view":
                    return self._send(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
                with tempfile.TemporaryDirectory(prefix="c2d-png-") as tmp:
                    h = Path(tmp) / "d.html"
                    h.write_text(html_text, encoding="utf-8")
                    try:
                        png = html_to_png(h, Path(tmp) / "d.png")
                    except Exception as e:  # noqa: BLE001
                        return self._page(500, "PNG failed", f"<h1>PNG failed</h1><pre>{htmllib.escape(str(e))}</pre>")
                    return self._send(200, png.read_bytes(), "image/png")
            if path == "/health":
                return self._send(200, b"ok", "text/plain")
            self._page(404, "Not found", f"<h1>Not found</h1><p><a href='/'>back</a></p>")

    return Handler


def serve(dirs: list[Path], host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), make_handler(dirs))
    print(f"iso-diagram service on http://{host}:{port}/  (dirs: {', '.join(map(str, dirs))})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
