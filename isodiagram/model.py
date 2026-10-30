"""Load + validate an *.iso.yaml file into a plain model."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from .kinds import KINDS, LAYER_COLORS, LINK_CLASSES, resolve_kind

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "iso-diagram.schema.json"


class _Loader(yaml.SafeLoader):
    """YAML 1.1 turns the bare keys `on` / `yes` / `no` into booleans, which would break `on: node`.
    Only true/false are booleans here."""


_Loader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:bool"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"), list("tTfF"))


class ModelError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass
class Node:
    id: str
    layer: int
    kind: str
    label: str
    level: int = 0
    note: str = ""
    group: str | None = None
    on: str | None = None
    mount: str | None = None
    icon: str | None = None
    color: str | None = None


@dataclass
class Group:
    id: str
    layer: int
    label: str
    kind: str = "group"
    color: str | None = None
    parent: str | None = None
    cols: int | None = None


@dataclass
class Layer:
    id: str
    index: int
    label: str
    color: str
    level: int = 0
    nodes: list[Node] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)


@dataclass
class Link:
    src: str
    dst: str
    label: str = ""
    cls: str = "default"
    bidirectional: bool = False
    dashed: bool | None = None
    implicit: bool = False


@dataclass
class Model:
    title: str
    subtitle: str
    theme: str
    layers: list[Layer]
    links: list[Link]
    warnings: list[str] = field(default_factory=list)
    nlevels: int = 1

    def node_map(self) -> dict[str, Node]:
        return {n.id: n for l in self.layers for n in l.nodes}


def load_text(text: str) -> Model:
    try:
        data = yaml.load(text, Loader=_Loader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as e:
        raise ModelError([f"YAML syntax error: {e}"])
    if not isinstance(data, dict):
        raise ModelError(["Top level of the file must be a mapping with a 'layers:' key."])

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errs = []
    for e in sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in e.absolute_path) or "(root)"
        errs.append(f"schema: {where}: {e.message}")
    if errs:
        raise ModelError(errs)
    return _build(data)


def load_file(path: str | Path) -> Model:
    return load_text(Path(path).read_text(encoding="utf-8"))


def _build(data: dict) -> Model:
    errors: list[str] = []
    warnings: list[str] = []
    layers: list[Layer] = []
    seen: dict[str, str] = {}  # id -> "layer:<x>" / "node" / "group"
    layer_ids: set[str] = set()
    level_index: dict[str, int] = {}

    for li, ld in enumerate(data["layers"]):
        if ld["id"] in layer_ids:
            errors.append(f"layers[{li}]: duplicate layer id '{ld['id']}'")
        layer_ids.add(ld["id"])
        layer = Layer(
            id=ld["id"], index=li, label=str(ld.get("label", ld["id"])),
            color=ld.get("color", LAYER_COLORS[li % len(LAYER_COLORS)]),
        )
        lkey = str(ld["level"]) if "level" in ld else f"@{li}"
        layer.level = level_index.setdefault(lkey, len(level_index))
        for gid, g in (ld.get("groups") or {}).items():
            g = g or {}
            if gid in seen:
                errors.append(f"layer '{layer.id}': id '{gid}' is already used (ids must be unique across nodes and groups)")
            seen[gid] = "group"
            layer.groups.append(Group(
                id=gid, layer=li, label=str(g.get("label", gid)), kind=g.get("kind", "group"),
                color=g.get("color"), parent=g.get("in"), cols=g.get("cols"),
            ))
        for nid, n in (ld.get("nodes") or {}).items():
            n = n or {}
            if nid in seen:
                errors.append(f"layer '{layer.id}': id '{nid}' is already used (ids must be unique across nodes and groups)")
            seen[nid] = "node"
            kind = resolve_kind(n.get("kind", ""))
            if kind is None:
                warnings.append(f"node '{nid}': unknown kind '{n.get('kind')}', using 'generic'. Known kinds: {', '.join(sorted(KINDS))}")
                kind = "generic"
            layer.nodes.append(Node(
                id=nid, layer=li, kind=kind, label=str(n.get("label", nid)), level=layer.level, note=n.get("note", ""),
                group=n.get("in"), on=n.get("on"), mount=n.get("mount"), icon=n.get("icon"), color=n.get("color"),
            ))
        layers.append(layer)

    nodes = {n.id: n for l in layers for n in l.nodes}
    groups = {g.id: g for l in layers for g in l.groups}

    for l in layers:
        for n in l.nodes:
            if n.group is not None:
                g = groups.get(n.group)
                if g is None:
                    errors.append(f"node '{n.id}': 'in: {n.group}' is not a group (groups are declared under 'groups:')")
                elif g.layer != l.index:
                    errors.append(f"node '{n.id}': group '{n.group}' is in layer '{layers[g.layer].id}', a node and its group must share a layer")
            for key, ref in (("on", n.on), ("mount", n.mount)):
                if ref is None:
                    continue
                if ref not in nodes:
                    errors.append(f"node '{n.id}': '{key}: {ref}' does not match any node id")
                elif ref == n.id:
                    errors.append(f"node '{n.id}': '{key}' cannot point to itself")
        for g in l.groups:
            if g.parent is not None:
                p = groups.get(g.parent)
                if p is None:
                    errors.append(f"group '{g.id}': 'in: {g.parent}' is not a group")
                elif p.layer != l.index:
                    errors.append(f"group '{g.id}': parent group '{g.parent}' is in a different layer")
    # cycles in group nesting
    for gid in groups:
        cur, hops = gid, 0
        while cur is not None and hops <= len(groups):
            cur = groups[cur].parent if cur in groups else None
            hops += 1
        if hops > len(groups):
            errors.append(f"group '{gid}': group nesting forms a cycle")
            break

    links: list[Link] = []
    for i, ld in enumerate(data.get("links") or []):
        for end in ("from", "to"):
            if ld[end] not in nodes:
                errors.append(f"links[{i}]: '{end}: {ld[end]}' does not match any node id")
        cls = ld.get("class", "default")
        if cls not in LINK_CLASSES:
            warnings.append(f"links[{i}]: unknown class '{cls}', using 'default'. Known: {', '.join(LINK_CLASSES)}")
            cls = "default"
        links.append(Link(ld["from"], ld["to"], str(ld.get("label", "")), cls, ld.get("bidirectional", False), ld.get("dashed")))

    # implicit vertical relations
    for n in nodes.values():
        if n.on and n.on in nodes:
            links.append(Link(n.id, n.on, "", "runs-on", implicit=True))
        if n.mount and n.mount in nodes:
            links.append(Link(n.id, n.mount, "", "storage", implicit=True, dashed=True))

    if errors:
        raise ModelError(errors)
    return Model(
        title=data.get("title", "Architecture"), subtitle=data.get("subtitle", ""),
        theme=data.get("theme", "light"), layers=layers, links=links, warnings=warnings,
        nlevels=len(level_index),
    )
