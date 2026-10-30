"""Model + layout + routes -> JSON-serialisable scene consumed by viewer/viewer.js."""
from __future__ import annotations

from .icons import load_icon
from .kinds import GROUP_COLORS, KINDS, LINK_CLASSES
from .layout import layout as do_layout
from .model import Model
from .route import route_all


def build_scene(model: Model) -> dict:
    lay = do_layout(model)
    paths = route_all(model, lay)
    warnings = list(model.warnings)
    icons: dict[str, dict] = {}

    def icon_key(key: str | None, owner: str) -> str | None:
        if not key:
            return None
        k = key if ":" in key else f"isoflow:{key}"
        if k not in icons:
            ic = load_icon(k)
            if ic is None:
                warnings.append(f"{owner}: icon '{key}' not found in assets/icons (run tools/fetch_assets.py?)")
                return None
            icons[k] = ic
        return k

    nodes = []
    link_ids: dict[str, list[int]] = {}
    for i, l in enumerate(model.links):
        link_ids.setdefault(l.src, []).append(i)
        link_ids.setdefault(l.dst, []).append(i)

    for layer in model.layers:
        for n in layer.nodes:
            spec = KINDS[n.kind]
            shape, color, glyph = spec["shape"], n.color or spec.get("color"), spec.get("glyph", "")
            key = icon_key(n.icon, f"node '{n.id}'") if n.icon else None
            if key is None and spec.get("icon"):
                key = icon_key(spec["icon"], f"node '{n.id}'")
            if n.icon and key:  # explicit override: isoflow art stays a sprite, everything else is a flat icon
                shape = "sprite" if key.startswith("isoflow:") else "tile"
            elif key is None and shape in ("sprite", "tile"):
                shape, glyph = "box", (n.kind[:3].upper())
            col, row = lay.node_pos[n.id]
            nodes.append({
                "id": n.id, "label": n.label, "kind": n.kind, "layer": layer.index, "level": layer.level, "col": col, "row": row,
                "shape": shape, "icon": key, "color": color, "glyph": glyph, "note": n.note,
                "group": n.group, "links": link_ids.get(n.id, []),
            })

    groups = []
    for layer in model.layers:
        for g in layer.groups:
            x0, z0, x1, z1, depth = lay.group_rects[g.id]
            groups.append({
                "id": g.id, "label": g.label, "layer": layer.index, "level": layer.level, "rect": [x0, z0, x1, z1], "depth": depth,
                "kind": g.kind, "color": g.color or GROUP_COLORS.get(g.kind, GROUP_COLORS["group"]),
            })

    links, classes = [], {}
    for i, (l, path) in enumerate(zip(model.links, paths)):
        color, dashed = LINK_CLASSES[l.cls]
        if l.dashed is not None:
            dashed = l.dashed
        classes[l.cls] = (color, dashed)
        links.append({
            "id": i, "from": l.src, "to": l.dst, "class": l.cls, "label": l.label, "color": color,
            "dashed": dashed, "both": l.bidirectional, "implicit": l.implicit,
            "arrow": not l.implicit or l.cls == "storage", "path": [list(p) for p in path],
        })

    # "decks": cells that links cross outside any plate (streets between plates) get a thin road tile
    plates_by_level: dict[int, list] = {}
    for l in model.layers:
        plates_by_level.setdefault(l.level, []).append(lay.plate_rects[l.id])
    deck_cells: set[tuple[int, int, int]] = set()
    for path in paths:
        for a, b in zip(path, path[1:]):
            if a[0] != b[0]:
                continue
            n = max(abs(a[1] - b[1]), abs(a[2] - b[2]))
            for t in range(n + 1):
                c = a[1] + (b[1] - a[1]) * t // max(n, 1)
                r = a[2] + (b[2] - a[2]) * t // max(n, 1)
                if not any(x0 <= c + 0.5 <= x1 and z0 <= r + 0.5 <= z1 for x0, z0, x1, z1 in plates_by_level[a[0]]):
                    deck_cells.add((a[0], c, r))
    decks = sorted(deck_cells)

    return {
        "title": model.title, "subtitle": model.subtitle, "theme": model.theme,
        "grid": {"w": lay.width, "d": lay.depth},
        "levels": model.nlevels, "decks": decks,
        "layers": [{"id": l.id, "label": l.label, "color": l.color, "index": l.index, "level": l.level,
                    "rect": list(lay.plate_rects[l.id])} for l in model.layers],
        "groups": groups, "nodes": nodes, "links": links, "icons": icons,
        "legend": [{"class": c, "color": v[0], "dashed": v[1]} for c, v in classes.items()],
        "warnings": warnings,
    }
