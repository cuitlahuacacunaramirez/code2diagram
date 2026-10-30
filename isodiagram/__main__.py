"""CLI:  python -m isodiagram <command> ...

  render   INPUT.iso.yaml [-o OUT.html] [--png OUT.png] [--size 1920x1080] [--scale 1]
  validate INPUT.iso.yaml
  scene    INPUT.iso.yaml            (dump the intermediate scene JSON)
  serve    [--dir DIR ...] [--port 8765]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import ModelError, build_scene, load_file, render_html

ROOT = Path(__file__).resolve().parent.parent


def _load(path: str):
    try:
        return load_file(path)
    except FileNotFoundError:
        sys.exit(f"error: file not found: {path}")
    except ModelError as e:
        print(f"{path}: invalid", file=sys.stderr)
        for m in e.errors:
            print(f"  - {m}", file=sys.stderr)
        sys.exit(2)


def cmd_validate(a) -> None:
    model = _load(a.input)
    n = sum(len(l.nodes) for l in model.layers)
    print(f"OK: {len(model.layers)} layers, {n} nodes, {len(model.links)} links")
    for w in model.warnings:
        print(f"  warning: {w}")


def cmd_scene(a) -> None:
    print(json.dumps(build_scene(_load(a.input)), indent=1))


def cmd_render(a) -> None:
    model = _load(a.input)
    scene = build_scene(model)
    src = Path(a.input)
    stem = src.name.split(".iso.")[0] if ".iso." in src.name else src.stem
    out = Path(a.output) if a.output else ROOT / "out" / f"{stem}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(scene), encoding="utf-8")
    print(f"html: {out}")
    for w in scene["warnings"]:
        print(f"  warning: {w}")
    if a.png is not None:
        from .png import html_to_png
        w, h = (int(x) for x in a.size.lower().split("x"))
        png = Path(a.png) if a.png else out.with_suffix(".png")
        html_to_png(out, png, w, h, a.scale)
        print(f"png:  {png}")


def cmd_serve(a) -> None:
    from .server import serve
    dirs = [Path(d).resolve() for d in (a.dir or [])] or [ROOT / "examples"]
    serve(dirs, a.host, a.port)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="isodiagram", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="YAML -> interactive HTML (+ optional PNG)")
    r.add_argument("input")
    r.add_argument("-o", "--output", help="HTML path (default: out/<name>.html)")
    r.add_argument("--png", nargs="?", const="", default=None, help="also write a PNG (optionally give the path)")
    r.add_argument("--size", default="1920x1080", help="PNG viewport, WxH")
    r.add_argument("--scale", type=float, default=1.0, help="PNG device scale factor (2 = retina)")
    r.set_defaults(fn=cmd_render)
    v = sub.add_parser("validate"); v.add_argument("input"); v.set_defaults(fn=cmd_validate)
    s = sub.add_parser("scene"); s.add_argument("input"); s.set_defaults(fn=cmd_scene)
    sv = sub.add_parser("serve", help="local web service that renders on demand")
    sv.add_argument("--dir", action="append", help="directory with *.iso.yaml (repeatable; default: examples/)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)
    sv.set_defaults(fn=cmd_serve)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
