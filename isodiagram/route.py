"""Orthogonal link routing on the per-layer grids.

Same-layer links: A* over free cells with a bend penalty and a penalty for cells/edges already used
(spreads parallel links over different lanes). Cross-layer links: horizontal in the source layer to a
"riser" cell, vertical riser, horizontal in the target layer.
"""
from __future__ import annotations

import heapq
from collections import deque

from .layout import Layout
from .model import Model

Cell = tuple[int, int]
Point = tuple[int, int, int]  # (level index, col, row)

BEND_COST = 1.2
USE_COST = 0.9


def _edge(a: Cell, b: Cell) -> tuple[Cell, Cell]:
    return (a, b) if a <= b else (b, a)


class Router:
    def __init__(self, model: Model, lay: Layout):
        self.w, self.d = lay.width, lay.depth
        self.pos = lay.node_pos
        self.bounds = lay.level_bounds
        self.blocked: list[set[Cell]] = [set() for _ in range(model.nlevels)]
        for l in model.layers:
            for n in l.nodes:
                self.blocked[l.level].add(self.pos[n.id])
        self.used: list[dict[tuple[Cell, Cell], int]] = [{} for _ in range(model.nlevels)]

    def _inb(self, level: int, c: Cell) -> bool:
        x0, z0, x1, z1 = self.bounds[level]
        return x0 <= c[0] < x1 and z0 <= c[1] < z1

    def _astar(self, layer: int, start: Cell, goal: Cell) -> list[Cell]:
        if start == goal:
            return [start]
        blocked, used = self.blocked[layer], self.used[layer]
        dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
        h = lambda c: abs(c[0] - goal[0]) + abs(c[1] - goal[1])
        pq = [(h(start), 0.0, start, -1)]
        best: dict[tuple[Cell, int], float] = {(start, -1): 0.0}
        parent: dict[tuple[Cell, int], tuple[Cell, int] | None] = {(start, -1): None}
        while pq:
            _, g, cell, di = heapq.heappop(pq)
            if cell == goal:
                path, key = [], (cell, di)
                while key is not None:
                    path.append(key[0])
                    key = parent[key]
                return path[::-1]
            if g > best.get((cell, di), 1e18):
                continue
            for ndi, (dx, dz) in enumerate(dirs):
                nc = (cell[0] + dx, cell[1] + dz)
                if not self._inb(layer, nc):
                    continue
                if nc in blocked and nc != goal:
                    continue
                cost = 1 + USE_COST * used.get(_edge(cell, nc), 0)
                if di not in (-1, ndi):
                    cost += BEND_COST
                ng = g + cost
                key = (nc, ndi)
                if ng < best.get(key, 1e18):
                    best[key] = ng
                    parent[key] = (cell, di)
                    heapq.heappush(pq, (ng + h(nc), ng, nc, ndi))
        return [start, goal]  # unreachable (should not happen on an open grid)

    def _mark(self, layer: int, path: list[Cell]) -> None:
        for a, b in zip(path, path[1:]):
            e = _edge(a, b)
            self.used[layer][e] = self.used[layer].get(e, 0) + 1

    def _riser_cell(self, ls: int, ld: int, src: Cell, dst: Cell) -> Cell:
        free = lambda l, c, own: self._inb(l, c) and (c == own or c not in self.blocked[l])
        if free(ls, dst, src):
            return dst
        if free(ld, src, dst):
            return src
        seen, q = {dst}, deque([dst])
        while q:
            c = q.popleft()
            if free(ls, c, src) and free(ld, c, dst):
                return c
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nc = (c[0] + dx, c[1] + dz)
                if 0 <= nc[0] < self.w and 0 <= nc[1] < self.d and nc not in seen:
                    seen.add(nc)
                    q.append(nc)
        return dst

    def route(self, ls: int, src: Cell, ld: int, dst: Cell) -> list[Point]:
        if ls == ld:
            path = self._astar(ls, src, dst)
            self._mark(ls, path)
            return _simplify([(ls, *c) for c in path])
        if src == dst:
            return [(ls, *src), (ld, *dst)]
        r = self._riser_cell(ls, ld, src, dst)
        p1 = self._astar(ls, src, r)
        self._mark(ls, p1)
        pts: list[Point] = [(ls, *c) for c in p1]
        pts.append((ld, *r))
        if r != dst:
            p2 = self._astar(ld, r, dst)
            self._mark(ld, p2)
            pts += [(ld, *c) for c in p2[1:]]
        return _simplify(pts)


def _simplify(pts: list[Point]) -> list[Point]:
    """Drop points lying in the middle of a straight run (same layer, same axis)."""
    if len(pts) <= 2:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[i], pts[i + 1]
        same_layer = a[0] == b[0] == c[0]
        if same_layer and ((a[1] == b[1] == c[1]) or (a[2] == b[2] == c[2])):
            continue
        out.append(b)
    out.append(pts[-1])
    return out


def route_all(model: Model, lay: Layout) -> list[list[Point]]:
    router = Router(model, lay)
    nodes = model.node_map()

    def span(l):
        a, b = lay.node_pos[l.src], lay.node_pos[l.dst]
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) + 3 * abs(nodes[l.src].level - nodes[l.dst].level)

    order = sorted(range(len(model.links)), key=lambda i: (model.links[i].implicit, span(model.links[i])))
    result: list[list[Point]] = [[] for _ in model.links]
    for i in order:
        l = model.links[i]
        s, d = nodes[l.src], nodes[l.dst]
        result[i] = router.route(s.level, lay.node_pos[s.id], d.level, lay.node_pos[d.id])
    return result
