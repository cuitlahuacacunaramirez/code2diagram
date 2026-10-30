"""Deterministic grid layout.

Every node occupies one cell. Blocks (groups / loose nodes) are shelf-packed with one empty cell between
them; the empty cells are the lanes the router uses. All layers share one slab size so they stack neatly.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .model import Group, Layer, Model, Node

PAD = 0.3  # how far a leaf group's rectangle extends past its outer cells


@dataclass
class Block:
    w: int
    d: int
    nodes: dict[str, tuple[int, int]] = field(default_factory=dict)
    groups: dict[str, tuple[float, float, float, float, int]] = field(default_factory=dict)  # rect + depth

    def shifted(self, dx: float, dz: float) -> "Block":
        return Block(
            self.w, self.d,
            {k: (x + dx, z + dz) for k, (x, z) in self.nodes.items()},
            {k: (a + dx, b + dz, c + dx, d + dz, dep) for k, (a, b, c, d, dep) in self.groups.items()},
        )


@dataclass
class Layout:
    width: int
    depth: int
    node_pos: dict[str, tuple[int, int]]
    group_rects: dict[str, tuple[float, float, float, float, int]]
    plate_rects: dict[str, tuple[float, float, float, float]]  # layer id -> rect (cells)
    level_bounds: list[tuple[int, int, int, int]]              # level -> (x0, z0, x1, z1) routable cells


def _pack(blocks: list[Block], target_w: int) -> Block:
    """Shelf-pack blocks left->right, top->bottom with 1 empty cell between them."""
    x = z = row_d = max_w = 0
    out = Block(0, 0)
    for b in blocks:
        if x > 0 and x + b.w > target_w:
            x, z, row_d = 0, z + row_d + 1, 0
        sb = b.shifted(x, z)
        out.nodes.update(sb.nodes)
        out.groups.update(sb.groups)
        x += b.w + 1
        row_d = max(row_d, b.d)
        max_w = max(max_w, x - 1)
    out.w, out.d = max_w, z + row_d
    return out


def _target(blocks: list[Block], factor: float) -> int:
    if not blocks:
        return 1
    area = sum((b.w + 1) * (b.d + 1) for b in blocks)
    return max(max(b.w for b in blocks), round(math.sqrt(area) * factor))


def _ordered(blocks: list[Block], key) -> list[Block]:
    """Stable sort: blocks whose nodes sit on something already placed go in that thing's order."""
    keys = [key(b) for b in blocks]
    idx = sorted(range(len(blocks)), key=lambda i: (keys[i] is None, keys[i] or (0, 0), i))
    return [blocks[i] for i in idx]


def _group_block(g: Group, layer: Layer, depth: int, child_groups: dict[str | None, list[Group]],
                 child_nodes: dict[str | None, list[Node]], key) -> Block:
    subs = _ordered([_group_block(c, layer, depth + 1, child_groups, child_nodes, key)
                     for c in child_groups.get(g.id, [])], key)
    leaves = _ordered([Block(1, 1, {n.id: (0, 0)}) for n in child_nodes.get(g.id, [])], key)
    m = 1 if subs else 0
    if g.cols and not subs:
        target = g.cols * 2 - 1
    else:
        target = _target(subs + leaves, 1.0 if not subs else 1.4)
    content = _pack(subs + leaves, target) if (subs or leaves) else Block(1, 1)
    inner = content.shifted(m, m)
    w, d = content.w + 2 * m, content.d + 2 * m
    rect = (0.0, 0.0, float(w), float(d)) if m else (-PAD, -PAD, w + PAD, d + PAD)
    out = Block(w, d, dict(inner.nodes), dict(inner.groups))
    out.groups[g.id] = (*rect, depth)
    return out


def _layer_block(layer: Layer, key) -> Block:
    child_groups: dict[str | None, list[Group]] = {}
    child_nodes: dict[str | None, list[Node]] = {}
    for g in layer.groups:
        child_groups.setdefault(g.parent, []).append(g)
    for n in layer.nodes:
        child_nodes.setdefault(n.group, []).append(n)
    blocks = _ordered([_group_block(g, layer, 0, child_groups, child_nodes, key) for g in child_groups.get(None, [])], key)
    blocks += _ordered([Block(1, 1, {n.id: (0, 0)}) for n in child_nodes.get(None, [])], key)
    if not blocks:
        return Block(1, 1)
    return _pack(blocks, _target(blocks, 1.5))


PLATE_MARGIN = 1   # empty cells between a plate's edge and its content
STREET = 3         # empty cells between plates on the same level (routing lanes / bridges)


def _arrange_plates(sizes: list[tuple[int, int]]) -> tuple[list[tuple[int, int]], int, int]:
    """Shelf-pack plates (w, d) with STREET cells between them -> offsets, total w, total d."""
    if len(sizes) == 1:
        return [(0, 0)], sizes[0][0], sizes[0][1]
    area = sum((w + STREET) * (d + STREET) for w, d in sizes)
    target = max(max(w for w, _ in sizes), round(math.sqrt(area) * 1.25))
    x = z = row_d = max_w = 0
    offs = []
    for w, d in sizes:
        if x > 0 and x + w > target:
            x, z, row_d = 0, z + row_d + STREET, 0
        offs.append((x, z))
        x += w + STREET
        row_d = max(row_d, d)
        max_w = max(max_w, x - STREET)
    return offs, max_w, z + row_d


def layout(model: Model) -> Layout:
    """Levels are laid out bottom -> top. Layers sharing a level become plates placed side by side.
    A node that is `on:` / `mount:`-ed on something already placed sorts by that target's (row, col),
    so risers tend to run straight up instead of sideways."""
    nodes = model.node_map()
    placed: dict[str, tuple[int, int]] = {}  # node id -> (row, col) in its level frame

    def key(b: Block):
        ks = []
        for nid in b.nodes:
            n = nodes[nid]
            for t in (n.on, n.mount):
                if t in placed:
                    ks.append(placed[t])
        return min(ks) if ks else None

    frames = []  # per level: (w, d, node_pos, groups, plates)
    for lv in range(model.nlevels):
        layers = [l for l in model.layers if l.level == lv]
        blocks = [_layer_block(l, key) for l in layers]
        m = PLATE_MARGIN
        offs, w, d = _arrange_plates([(b.w + 2 * m, b.d + 2 * m) for b in blocks])
        npos: dict[str, tuple[float, float]] = {}
        grps: dict[str, tuple[float, float, float, float, int]] = {}
        plates: dict[str, tuple[float, float, float, float]] = {}
        for l, b, (ox, oz) in zip(layers, blocks, offs):
            sb = b.shifted(ox + m, oz + m)
            npos.update(sb.nodes)
            grps.update(sb.groups)
            plates[l.id] = (ox, oz, ox + b.w + 2 * m, oz + b.d + 2 * m)
        for nid, (x, z) in npos.items():
            placed[nid] = (z, x)
        frames.append((w, d, npos, grps, plates))

    width = max(f[0] for f in frames) + 2
    depth = max(f[1] for f in frames) + 2
    node_pos: dict[str, tuple[int, int]] = {}
    group_rects: dict[str, tuple[float, float, float, float, int]] = {}
    plate_rects: dict[str, tuple[float, float, float, float]] = {}
    bounds: list[tuple[int, int, int, int]] = []
    for w, d, npos, grps, plates in frames:
        ox, oz = (width - w) // 2, (depth - d) // 2
        node_pos.update({k: (int(x) + ox, int(z) + oz) for k, (x, z) in npos.items()})
        group_rects.update({k: (a + ox, b + oz, c + ox, e + oz, dep) for k, (a, b, c, e, dep) in grps.items()})
        plate_rects.update({k: (a + ox, b + oz, c + ox, e + oz) for k, (a, b, c, e) in plates.items()})
        bounds.append((ox, oz, ox + w, oz + d))
    return Layout(width, depth, node_pos, group_rects, plate_rects, bounds)
