"""Vocabulary: node kinds -> how they are drawn.

shape:
  sprite  pre-drawn isometric illustration (Isoflow pack), billboarded on a base tile
  tile    flat icon projected onto the top face of a low coloured tile
  box     procedural extruded box with a text glyph on the top face
  cyl     procedural cylinder with a text glyph on the top face
  rack    procedural tall box (server rack look)
"""
from __future__ import annotations

from typing import Any

# kind -> spec.  icon is "<pack>:<id>"; glyph is the text shown on procedural shapes.
KINDS: dict[str, dict[str, Any]] = {
    # --- hardware ---
    "rack":            {"shape": "rack", "color": "#475569", "glyph": "RACK"},
    "server":          {"shape": "sprite", "icon": "isoflow:server"},
    "gpu":             {"shape": "box", "color": "#16a34a", "glyph": "GPU"},
    "storage":         {"shape": "sprite", "icon": "isoflow:storage"},
    "nas":             {"shape": "sprite", "icon": "isoflow:storage"},
    "san":             {"shape": "sprite", "icon": "isoflow:storage"},
    "vm":              {"shape": "sprite", "icon": "isoflow:vm"},
    # --- network ---
    "switch":          {"shape": "sprite", "icon": "isoflow:switch-module"},
    "router":          {"shape": "sprite", "icon": "isoflow:router"},
    "load-balancer":   {"shape": "sprite", "icon": "isoflow:loadbalancer"},
    "dns":             {"shape": "sprite", "icon": "isoflow:dns"},
    "vpn":             {"shape": "sprite", "icon": "isoflow:lock"},
    "internet":        {"shape": "sprite", "icon": "isoflow:cloud"},
    "cloud":           {"shape": "sprite", "icon": "isoflow:cloud"},
    # --- security ---
    "firewall":        {"shape": "sprite", "icon": "isoflow:firewall"},
    "waf":             {"shape": "sprite", "icon": "isoflow:firewall"},
    "vault":           {"shape": "sprite", "icon": "isoflow:lock"},
    "ids":             {"shape": "box", "color": "#dc2626", "glyph": "IDS"},
    # --- kubernetes ---
    "k8s-cluster":     {"shape": "tile", "icon": "kubernetes:_k8s_", "color": "#326ce5"},
    "k8s-control-plane": {"shape": "tile", "icon": "kubernetes:k8s-control-plane", "color": "#326ce5"},
    "k8s-node":        {"shape": "tile", "icon": "kubernetes:k8s-node", "color": "#326ce5"},
    "k8s-namespace":   {"shape": "tile", "icon": "kubernetes:k8s-ns", "color": "#326ce5"},
    "k8s-api":         {"shape": "tile", "icon": "kubernetes:k8s-api", "color": "#326ce5"},
    "k8s-etcd":        {"shape": "tile", "icon": "kubernetes:k8s-etcd", "color": "#326ce5"},
    "k8s-scheduler":   {"shape": "tile", "icon": "kubernetes:k8s-sched", "color": "#326ce5"},
    "pod":             {"shape": "tile", "icon": "kubernetes:k8s-pod", "color": "#326ce5"},
    "deployment":      {"shape": "tile", "icon": "kubernetes:k8s-deploy", "color": "#326ce5"},
    "statefulset":     {"shape": "tile", "icon": "kubernetes:k8s-sts", "color": "#326ce5"},
    "daemonset":       {"shape": "tile", "icon": "kubernetes:k8s-ds", "color": "#326ce5"},
    "replicaset":      {"shape": "tile", "icon": "kubernetes:k8s-rs", "color": "#326ce5"},
    "k8s-service":     {"shape": "tile", "icon": "kubernetes:k8s-svc", "color": "#326ce5"},
    "ingress":         {"shape": "tile", "icon": "kubernetes:k8s-ing", "color": "#326ce5"},
    "pvc":             {"shape": "tile", "icon": "kubernetes:k8s-pvc", "color": "#d97706"},
    "pv":              {"shape": "tile", "icon": "kubernetes:k8s-pv", "color": "#d97706"},
    "storageclass":    {"shape": "tile", "icon": "kubernetes:k8s-sc", "color": "#d97706"},
    "volume":          {"shape": "tile", "icon": "kubernetes:k8s-vol", "color": "#d97706"},
    "configmap":       {"shape": "tile", "icon": "kubernetes:k8s-cm", "color": "#326ce5"},
    "secret":          {"shape": "tile", "icon": "kubernetes:k8s-secret", "color": "#326ce5"},
    "k8s-job":         {"shape": "tile", "icon": "kubernetes:k8s-job", "color": "#326ce5"},
    "k8s-cronjob":     {"shape": "tile", "icon": "kubernetes:k8s-cronjob", "color": "#326ce5"},
    "hpa":             {"shape": "tile", "icon": "kubernetes:k8s-hpa", "color": "#326ce5"},
    "networkpolicy":   {"shape": "tile", "icon": "kubernetes:k8s-netpol", "color": "#326ce5"},
    # --- workloads ---
    "microservice":    {"shape": "box", "color": "#2563eb", "glyph": "SVC"},
    "llm":             {"shape": "box", "color": "#7c3aed", "glyph": "LLM"},
    "gateway":         {"shape": "box", "color": "#0891b2", "glyph": "GW"},
    "function":        {"shape": "sprite", "icon": "isoflow:function-module"},
    "queue":           {"shape": "sprite", "icon": "isoflow:queue"},
    "job":             {"shape": "sprite", "icon": "isoflow:cronjob"},
    # --- data ---
    "database":        {"shape": "cyl", "color": "#0d9488", "glyph": "DB"},
    "datasource":      {"shape": "cyl", "color": "#0284c7", "glyph": "SRC"},
    "cache":           {"shape": "sprite", "icon": "isoflow:cache"},
    "object-store":    {"shape": "sprite", "icon": "isoflow:storage"},
    "document":        {"shape": "sprite", "icon": "isoflow:document"},
    # --- experience ---
    "ui":              {"shape": "sprite", "icon": "isoflow:desktop"},
    "api":             {"shape": "box", "color": "#ea580c", "glyph": "API"},
    "user":            {"shape": "sprite", "icon": "isoflow:user"},
    "laptop":          {"shape": "sprite", "icon": "isoflow:laptop"},
    "mobile":          {"shape": "sprite", "icon": "isoflow:mobiledevice"},
    "external":        {"shape": "sprite", "icon": "isoflow:cloud"},
    # --- generic ---
    "generic":         {"shape": "sprite", "icon": "isoflow:cube"},
}

ALIASES = {
    "k8s-ns": "k8s-namespace", "k8s-cp": "k8s-control-plane", "k8s-svc": "k8s-service",
    "svc": "microservice", "db": "database", "lb": "load-balancer", "fw": "firewall",
    "users": "user", "node": "k8s-node", "cluster": "k8s-cluster", "service": "k8s-service",
    "control-plane": "k8s-control-plane", "namespace": "k8s-namespace", "ingress-controller": "ingress",
    "web": "ui", "frontend": "ui", "frontend-ui": "ui", "redis": "cache", "s3": "object-store",
    "bucket": "object-store", "kafka": "queue", "mq": "queue", "model": "llm", "inference": "llm",
    "physical-server": "server", "bare-metal": "server", "nvidia-gpu": "gpu",
}

# link class -> (colour, dashed)
LINK_CLASSES: dict[str, tuple[str, bool]] = {
    "internal":   ("#2563eb", False),
    "external":   ("#ea580c", False),
    "data":       ("#0d9488", False),
    "control":    ("#7c3aed", False),
    "storage":    ("#d97706", False),
    "management": ("#64748b", True),
    "runs-on":    ("#94a3b8", True),
    "default":    ("#475569", False),
}

GROUP_COLORS = {
    "zone": "#f97316", "cluster": "#326ce5", "namespace": "#0ea5e9", "rack": "#64748b",
    "vlan": "#a855f7", "group": "#94a3b8",
}

LAYER_COLORS = ["#dbeafe", "#dcfce7", "#fef3c7", "#fce7f3", "#ede9fe", "#e0f2fe", "#fee2e2", "#ccfbf1"]


def resolve_kind(kind: str) -> str | None:
    k = (kind or "").strip().lower()
    k = ALIASES.get(k, k)
    return k if k in KINDS else None
