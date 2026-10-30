// iso-diagram viewer: renders the scene JSON (see isodiagram/scene.py) with three.js.
import * as THREE from 'three';
import { OrbitControls } from 'orbit';

const S = JSON.parse(document.getElementById('scene').textContent);
const CLEAN = location.hash.includes('clean');
if (CLEAN) document.body.classList.add('clean');

// ---------------------------------------------------------------- constants
const LAYER_GAP = Math.max(3.7, 0.2 * (S.grid.w + S.grid.d));   // levels spread with the footprint so wide plates do not hide each other
const SLAB_H = 0.22;
const LINK_Y = 0.18;        // links float slightly above the slab
const PXU = 120;            // label pixels per world unit
const THEMES = {
  light: { bg: 0xf3f5f9, ink: '#0f172a', sub: '#475569', slabMix: 0.0, grid: 0x64748b, slabOpacity: 0.5,
           pill: 'rgba(255,255,255,.94)', pillInk: '#0f172a', base: 0xffffff },
  dark:  { bg: 0x0b1220, ink: '#e2e8f0', sub: '#94a3b8', slabMix: 0.62, grid: 0x94a3b8, slabOpacity: 0.6,
           pill: 'rgba(15,23,42,.94)', pillInk: '#e2e8f0', base: 0x1e293b },
};

const state = {
  theme: S.theme === 'dark' ? 'dark' : 'light',
  explode: 1,
  labels: true,
  hidden: new Set(),
  vlinks: true,
  hover: null,
  pinned: null,
};

// ---------------------------------------------------------------- renderer / camera
const canvas = document.getElementById('view');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
// Software WebGL (Citrix, no GPU) is fill-rate bound: render at 1x while the user drags/zooms, sharp when idle.
const DPR_IDLE = Math.min(Math.max(window.devicePixelRatio || 1, 1.5), 2);
renderer.setPixelRatio(DPR_IDLE);
let idleTimer = null;
function setDpr(r) {
  if (renderer.getPixelRatio() === r) return;
  renderer.setPixelRatio(r);
  renderer.setSize(window.innerWidth, window.innerHeight, false);
}
const scene = new THREE.Scene();
const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, -500, 500);
const ISO_DIR = new THREE.Vector3(1, Math.SQRT2 * Math.tan(THREE.MathUtils.degToRad(30)), 1).normalize();
const controls = new OrbitControls(camera, canvas);
controls.screenSpacePanning = true;
controls.minZoom = 0.2;
controls.maxZoom = 12;
controls.addEventListener('change', requestRender);
controls.addEventListener('start', () => { clearTimeout(idleTimer); setDpr(1); });
controls.addEventListener('end', () => {
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => { setDpr(DPR_IDLE); requestRender(); }, 200);
});

const sun = new THREE.DirectionalLight(0xffffff, 0.85);
sun.position.set(-0.35, 1, 0.9);
scene.add(new THREE.AmbientLight(0xffffff, 0.78), sun);

const NODE = Object.fromEntries(S.nodes.map(n => [n.id, n]));
const W = S.grid.w, D = S.grid.d;
const OX = -W / 2, OZ = -D / 2;
const layerY = i => i * LAYER_GAP * state.explode;
const cellPos = (c, r) => new THREE.Vector3(c + 0.5 + OX, 0, r + 0.5 + OZ);

// ---------------------------------------------------------------- helpers
function mix(hex, toHex, t) {
  return new THREE.Color(hex).lerp(new THREE.Color(toHex), t);
}
function loadImage(uri) {
  return new Promise((res, rej) => {
    const img = new Image();
    img.onload = () => res(img);
    img.onerror = () => rej(new Error('icon failed to load'));
    img.src = uri;
  });
}
const iconCanvas = {};   // key -> {canvas, aspect}
async function prepareIcons() {
  await Promise.all(Object.entries(S.icons).map(async ([key, ic]) => {
    try {
      const img = await loadImage(ic.uri);
      const aspect = ic.w / ic.h;
      const cw = key.startsWith('isoflow:') ? 1024 : 512;
      const ch = pow2(Math.round(cw / aspect));   // power-of-two canvas; the plane keeps the true aspect
      const c = document.createElement('canvas');
      c.width = cw; c.height = ch;
      c.getContext('2d').drawImage(img, 0, 0, cw, ch);
      iconCanvas[key] = { canvas: c, aspect };
    } catch (e) { console.warn(key, e); }
  }));
}
const pow2 = n => 2 ** Math.ceil(Math.log2(Math.max(2, n)));
const texCache = new Map();   // shared icon textures, kept across rebuilds
function tex(canvasEl, key) {
  if (key && texCache.has(key)) return texCache.get(key);
  const t = new THREE.CanvasTexture(canvasEl);
  t.colorSpace = THREE.SRGBColorSpace;
  t.generateMipmaps = true;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.magFilter = THREE.LinearFilter;
  t.anisotropy = renderer.capabilities.getMaxAnisotropy();
  if (key) { t.userData.shared = true; texCache.set(key, t); }
  return t;
}
function textCanvas(text, o = {}) {
  const font = o.font || 26, weight = o.weight || 600, pad = o.pad ?? 9, maxW = o.maxW || 260, k = 3;
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d');
  const f = `${weight} ${font}px "Segoe UI", system-ui, sans-serif`;
  ctx.font = f;
  const words = String(text).split(/\s+/), lines = [];
  let cur = '';
  for (const w of words) {
    const t = cur ? cur + ' ' + w : w;
    if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t;
  }
  if (cur) lines.push(cur);
  const tw = Math.min(maxW, Math.max(...lines.map(l => ctx.measureText(l).width)));
  const w = Math.ceil(tw + pad * 2), h = Math.ceil(lines.length * font * 1.22 + pad * 1.4);
  const cw = pow2(w * k), ch = pow2(h * k);   // power-of-two so mipmaps work; the plane maps it back to w x h
  c.width = cw; c.height = ch;
  ctx.scale(cw / w, ch / h);
  if (o.bg) {
    ctx.fillStyle = o.bg;
    const r = o.radius ?? 10;
    ctx.beginPath(); ctx.roundRect(0.5, 0.5, w - 1, h - 1, r); ctx.fill();
    if (o.border) { ctx.strokeStyle = o.border; ctx.lineWidth = 1; ctx.stroke(); }
  }
  ctx.font = f; ctx.fillStyle = o.color || '#000'; ctx.textBaseline = 'middle';
  ctx.textAlign = o.align || 'center';
  const x = ctx.textAlign === 'center' ? w / 2 : pad;
  lines.forEach((l, i) => ctx.fillText(l, x, pad * 0.7 + font * 1.22 * (i + 0.5)));
  return { canvas: c, w, h };
}

// ---------------------------------------------------------------- scene graph (rebuilt on theme/explode change)
let root = null;
let linkGroup = null;
let billboards = [];          // { obj, anchor, up, right, space }
const nodeRec = {};           // id -> { group, mats:[[mat,base]], pick, ring, label }
const linkRec = [];           // id -> { group, mats, labelMats, layers:Set }
const picks = [];

function disposeTree(o) {
  o.traverse(c => {
    c.geometry?.dispose?.();
    const m = c.material;
    (Array.isArray(m) ? m : m ? [m] : []).forEach(mm => { if (!mm.map?.userData.shared) mm.map?.dispose?.(); mm.dispose?.(); });
  });
}

function billboard(parent, mesh, anchor, up = 0, right = 0) {
  mesh.userData.bb = true;
  parent.add(mesh);
  const rec = { obj: mesh, anchor: anchor.clone(), up, right };
  billboards.push(rec);
  return rec;
}
function labelMesh(text, o, order) {
  const t = textCanvas(text, o);
  const mat = new THREE.MeshBasicMaterial({ map: tex(t.canvas), transparent: true, depthTest: false, depthWrite: false });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(t.w / PXU, t.h / PXU), mat);
  m.renderOrder = order;
  m.userData.size = [t.w / PXU, t.h / PXU];
  return { mesh: m, mat };
}
function rrShape(x0, z0, x1, z1, r) {
  // Shape drawn in (x, -z) so rotating it by -90deg about X lays it on the XZ plane.
  const s = new THREE.Shape();
  const ya = -z0, yb = -z1;
  const lo = Math.min(ya, yb), hi = Math.max(ya, yb);
  s.moveTo(x0 + r, lo); s.lineTo(x1 - r, lo); s.quadraticCurveTo(x1, lo, x1, lo + r);
  s.lineTo(x1, hi - r); s.quadraticCurveTo(x1, hi, x1 - r, hi); s.lineTo(x0 + r, hi);
  s.quadraticCurveTo(x0, hi, x0, hi - r); s.lineTo(x0, lo + r); s.quadraticCurveTo(x0, lo, x0 + r, lo);
  return s;
}

function build() {
  const th = THEMES[state.theme];
  document.documentElement.dataset.theme = state.theme;
  if (root) { scene.remove(root); disposeTree(root); }
  if (linkGroup) { scene.remove(linkGroup); disposeTree(linkGroup); }
  billboards = []; picks.length = 0;
  for (const k in nodeRec) delete nodeRec[k];
  scene.background = new THREE.Color(th.bg);
  root = new THREE.Group();
  scene.add(root);

  const layerGroups = S.layers.map(l => {
    const g = new THREE.Group();
    g.position.y = layerY(l.level);
    g.userData.layer = l.index;
    root.add(g);
    return g;
  });

  // plates (one slab per layer; layers sharing a level sit side by side), grid, plate titles
  for (const l of S.layers) {
    const g = layerGroups[l.index];
    const base = l.level * 20;
    const [x0, z0, x1, z1] = l.rect;
    const pw = x1 - x0, pd = z1 - z0;
    const col = mix(l.color, 0x0b1220, th.slabMix);
    const slab = new THREE.Mesh(new THREE.BoxGeometry(pw, SLAB_H, pd),
      new THREE.MeshLambertMaterial({ color: col, transparent: true, opacity: th.slabOpacity, depthWrite: false }));
    slab.position.set(OX + x0 + pw / 2, -SLAB_H / 2, OZ + z0 + pd / 2); slab.renderOrder = base;
    g.add(slab);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(slab.geometry),
      new THREE.LineBasicMaterial({ color: th.grid, transparent: true, opacity: 0.45 }));
    edges.position.copy(slab.position); edges.renderOrder = base + 1;
    g.add(edges);
    const pts = [];
    for (let i = 1; i < pw; i++) pts.push(OX + x0 + i, 0.004, OZ + z0, OX + x0 + i, 0.004, OZ + z1);
    for (let j = 1; j < pd; j++) pts.push(OX + x0, 0.004, OZ + z0 + j, OX + x1, 0.004, OZ + z0 + j);
    const gg = new THREE.BufferGeometry();
    gg.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    const grid = new THREE.LineSegments(gg, new THREE.LineBasicMaterial({ color: th.grid, transparent: true, opacity: 0.16 }));
    grid.renderOrder = base + 1;
    g.add(grid);
    const t = labelMesh(l.label.toUpperCase(), { font: 34, weight: 700, color: th.pillInk, bg: th.pill, pad: 12, radius: 12, border: 'rgba(100,116,139,.5)', maxW: 420 }, 1150);
    billboard(g, t.mesh, new THREE.Vector3(OX + x0, 0.1, OZ + z1), 0.34, -t.mesh.userData.size[0] / 2 - 0.1);
  }

  // road decks: cells that links cross between plates of the same level
  const byLevel = {};
  for (const [lv, c, r] of S.decks) (byLevel[lv] ||= []).push([c, r]);
  for (const lv in byLevel) {
    const cells = byLevel[lv];
    const geo = new THREE.BoxGeometry(0.36, 0.06, 0.36);
    const inst = new THREE.InstancedMesh(geo, new THREE.MeshLambertMaterial({ color: state.theme === 'dark' ? 0x334155 : 0xcbd5e1 }), cells.length);
    const m4 = new THREE.Matrix4();
    cells.forEach(([c, r], k) => { m4.makeTranslation(c + 0.5 + OX, -0.04, r + 0.5 + OZ); inst.setMatrixAt(k, m4); });
    inst.frustumCulled = false; inst.renderOrder = lv * 20 + 1;
    const dg = new THREE.Group(); dg.userData.layer = -1; dg.position.y = layerY(+lv); dg.add(inst);
    root.add(dg);
  }

  // groups
  for (const gr of S.groups) {
    const g = layerGroups[gr.layer];
    const [x0, z0, x1, z1] = gr.rect;
    const y = 0.02 + gr.depth * 0.012 + 0.0;
    const base = gr.level * 20 + 2;
    const col = mix(gr.color, 0x0b1220, state.theme === 'dark' ? 0.25 : 0);
    const fill = new THREE.Mesh(new THREE.ShapeGeometry(rrShape(x0 + OX, z0 + OZ, x1 + OX, z1 + OZ, 0.3)),
      new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.2, depthWrite: false, side: THREE.DoubleSide }));
    fill.rotation.x = -Math.PI / 2; fill.position.y = y; fill.renderOrder = base;
    g.add(fill);
    const sp = rrShape(x0 + OX, z0 + OZ, x1 + OX, z1 + OZ, 0.3).getPoints(10).map(p => new THREE.Vector3(p.x, y + 0.002, -p.y));
    const line = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(sp),
      new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.85 }));
    line.renderOrder = base + 1;
    g.add(line);
    const t = labelMesh(gr.label, { font: 25, weight: 700, color: '#fff', bg: col.getStyle(), pad: 7, radius: 8, maxW: 260 }, 1150);
    billboard(g, t.mesh, new THREE.Vector3(x0 + OX, y, z1 + OZ), t.mesh.userData.size[1] / 2 + 0.06, t.mesh.userData.size[0] / 2 + 0.05);
  }

  // nodes
  for (const n of S.nodes) buildNode(layerGroups[n.layer], n, th);

  linkGroup = new THREE.Group();
  scene.add(linkGroup);
  buildLinks(th);
  applyVisibility();
  applyFocus();
  requestRender();
}

function yawFlat(m) {            // lay a plane on the top face, upright on screen
  m.rotation.order = 'YXZ';
  m.rotation.set(-Math.PI / 2, Math.PI / 4, 0);
}

function buildNode(g, n, th) {
  const grp = new THREE.Group();
  const p = cellPos(n.col, n.row);
  grp.position.copy(p);
  g.add(grp);
  const rec = { group: grp, mats: [], pick: null, ring: null, label: null, world: p };
  nodeRec[n.id] = rec;
  const order = n.level * 20 + 5;
  const track = (mat, base = 1) => { mat.transparent = true; rec.mats.push([mat, base]); return mat; };
  const col = new THREE.Color(n.color || '#64748b');
  const lam = (c, extra = {}) => track(new THREE.MeshLambertMaterial({ color: c, ...extra }));
  let topY = 0.12;

  // base tile (soft rounded square under every node)
  const tile = new THREE.Mesh(new THREE.ShapeGeometry(rrShape(-0.47, -0.47, 0.47, 0.47, 0.12)),
    track(new THREE.MeshBasicMaterial({ color: th.base, opacity: 0.55, depthWrite: false, side: THREE.DoubleSide }), 0.55));
  tile.rotation.x = -Math.PI / 2; tile.position.y = 0.025; tile.renderOrder = order - 1;
  grp.add(tile);

  if (n.shape === 'sprite' && iconCanvas[n.icon]) {
    const { canvas: ic, aspect } = iconCanvas[n.icon];
    const wP = n.icon.startsWith('isoflow:') ? 1.7 : 1.2, hP = wP / aspect;
    const mat = track(new THREE.MeshBasicMaterial({ map: tex(ic, n.icon), depthWrite: false }));
    const m = new THREE.Mesh(new THREE.PlaneGeometry(wP, hP), mat);
    m.renderOrder = order + 1;
    billboard(grp, m, new THREE.Vector3(0, 0.05, 0), hP / 2 - wP * 0.27, 0);
    topY = Math.min(hP, 1.2);
  } else if (n.shape === 'tile') {
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.84, 0.16, 0.84), lam(col.clone().lerp(new THREE.Color(0xffffff), 0.86)));
    body.position.y = 0.1; grp.add(body);
    const rim = new THREE.Mesh(new THREE.BoxGeometry(0.86, 0.04, 0.86), lam(col));
    rim.position.y = 0.04; grp.add(rim);
    if (iconCanvas[n.icon]) {
      const { canvas: ic, aspect } = iconCanvas[n.icon];
      const s = 0.62;
      const f = new THREE.Mesh(new THREE.PlaneGeometry(s * Math.min(1, aspect), s / Math.max(1, aspect)),
        track(new THREE.MeshBasicMaterial({ map: tex(ic, n.icon), depthWrite: false })));
      yawFlat(f); f.position.y = 0.2; f.renderOrder = order + 1;
      grp.add(f);
    }
    topY = 0.3;
  } else {
    let body, h;
    if (n.shape === 'cyl') { h = 0.72; body = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, h, 40), lam(col)); }
    else if (n.shape === 'rack') { h = 1.35; body = new THREE.Mesh(new THREE.BoxGeometry(0.72, h, 0.78), lam(col)); }
    else { h = 0.62; body = new THREE.Mesh(new THREE.BoxGeometry(0.8, h, 0.8), lam(col)); }
    body.position.y = h / 2 + 0.03; grp.add(body);
    if (n.shape === 'rack') {
      for (let i = 0; i < 5; i++) {
        const u = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.07, 0.03), lam(col.clone().lerp(new THREE.Color(0xffffff), 0.55)));
        u.position.set(0, 0.25 + i * 0.22, 0.4); grp.add(u);
      }
    }
    const gt = textCanvas(n.glyph || '', { font: 54, weight: 800, color: '#ffffff', maxW: 200, pad: 4 });
    const sz = n.shape === 'rack' ? 0.5 : 0.52;
    const f = new THREE.Mesh(new THREE.PlaneGeometry(sz, sz * gt.h / gt.w),
      track(new THREE.MeshBasicMaterial({ map: tex(gt.canvas), depthWrite: false })));
    yawFlat(f); f.position.y = h + 0.04; f.renderOrder = order + 1;
    grp.add(f);
    topY = h + 0.1;
  }

  // label under the node
  if (n.label) {
    const t = labelMesh(n.label, { font: 25, weight: 600, color: th.pillInk, bg: th.pill, pad: 7, radius: 8, maxW: 210, border: 'rgba(100,116,139,.35)' }, 1200);
    rec.label = billboard(grp, t.mesh, new THREE.Vector3(0, 0, 0), -0.7, 0);
    rec.labelMat = t.mat; rec.mats.push([t.mat, 1]);
  }

  // hover ring
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.56, 0.64, 4, 1, Math.PI / 4),
    new THREE.MeshBasicMaterial({ color: 0x2563eb, side: THREE.DoubleSide, transparent: true, opacity: 0.9, depthTest: false }));
  ring.rotation.x = -Math.PI / 2; ring.position.y = 0.05; ring.visible = false; ring.renderOrder = 900;
  grp.add(ring); rec.ring = ring;

  // invisible pick volume
  const pick = new THREE.Mesh(new THREE.BoxGeometry(0.95, Math.max(0.6, topY), 0.95), new THREE.MeshBasicMaterial({ visible: false }));
  pick.position.y = Math.max(0.6, topY) / 2; pick.userData.nodeId = n.id; grp.add(pick);
  rec.pick = pick; picks.push(pick);
}

// ---------------------------------------------------------------- links
const UP = new THREE.Vector3(0, 1, 0);
const _q = new THREE.Quaternion();
function segGeo(a, b, r) {
  const d = new THREE.Vector3().subVectors(b, a);
  const len = d.length();
  if (len < 1e-4) return null;
  const g = new THREE.CylinderGeometry(r, r, len, 8, 1);
  g.applyQuaternion(_q.setFromUnitVectors(UP, d.normalize()));
  g.translate((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2);
  return g;
}
function arrowGeo(tip, dir, r) {
  const h = r * 5.2;
  const g = new THREE.ConeGeometry(r * 2.6, h, 14);
  g.applyQuaternion(_q.setFromUnitVectors(UP, dir.clone().normalize()));
  const c = tip.clone().addScaledVector(dir, -h / 2);
  g.translate(c.x, c.y, c.z);
  return g;
}
function mergeGeoms(list) {   // all inputs are indexed three.js primitives; one draw call per link
  const pos = [], idx = [];
  let off = 0;
  for (const g of list) {
    const p = g.attributes.position.array;
    for (let i = 0; i < p.length; i++) pos.push(p[i]);
    const ix = g.index.array;
    for (let i = 0; i < ix.length; i++) idx.push(ix[i] + off);
    off += p.length / 3;
    g.dispose();
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  out.setIndex(idx);
  return out;
}

function buildLinks(th) {
  linkRec.length = 0;
  for (const L of S.links) {
    const grp = new THREE.Group();
    const mats = [];
    const geoms = [];
    const col = new THREE.Color(L.color);
    if (state.theme === 'dark') col.lerp(new THREE.Color(0xffffff), 0.3);
    const mat = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.95, depthWrite: false });
    mats.push(mat);
    const r = L.implicit ? 0.028 : 0.042;
    const pts = L.path.map(([l, c, rr]) => {
      const p = cellPos(c, rr); p.y = layerY(l) + LINK_Y; return p;
    });
    // trim horizontal ends so the line stops at the tile edge instead of the node centre
    const trim = (i, j, amount) => {
      const a = pts[i], b = pts[j];
      if (Math.abs(a.y - b.y) > 1e-6) return;
      const d = new THREE.Vector3().subVectors(b, a); const len = d.length();
      const t = Math.min(amount, len * 0.45);
      a.addScaledVector(d.normalize(), t);
    };
    if (pts.length >= 2) {
      trim(0, 1, 0.5);
      trim(pts.length - 1, pts.length - 2, L.arrow ? 0.52 : 0.4);
    }
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1];
      const vertical = Math.abs(a.y - b.y) > 1e-6;
      if (L.dashed) {
        const d = new THREE.Vector3().subVectors(b, a); const len = d.length(); const dir = d.clone().normalize();
        const step = vertical ? 0.34 : 0.28, on = step * 0.58;
        for (let t = 0; t < len; t += step) {
          const g = segGeo(a.clone().addScaledVector(dir, t), a.clone().addScaledVector(dir, Math.min(t + on, len)), r);
          if (g) geoms.push(g);
        }
      } else {
        const g = segGeo(a, b, r); if (g) geoms.push(g);
      }
      if (i > 0) { const sg = new THREE.SphereGeometry(r * 1.02, 8, 6); sg.translate(a.x, a.y, a.z); geoms.push(sg); }
    }
    if (L.arrow && pts.length >= 2) {
      const n = pts.length;
      geoms.push(arrowGeo(pts[n - 1], new THREE.Vector3().subVectors(pts[n - 1], pts[n - 2]).normalize(), r));
      if (L.both) geoms.push(arrowGeo(pts[0], new THREE.Vector3().subVectors(pts[0], pts[1]).normalize(), r));
    }
    if (geoms.length) { const lm = new THREE.Mesh(mergeGeoms(geoms), mat); lm.renderOrder = 1000; grp.add(lm); }
    // label on the longest horizontal run
    const labelMats = [];
    if (L.label) {
      let best = null, bl = -1;
      for (let i = 0; i < pts.length - 1; i++) {
        const len = pts[i].distanceTo(pts[i + 1]);
        if (Math.abs(pts[i].y - pts[i + 1].y) < 1e-6 && len > bl) { bl = len; best = i; }
      }
      const i = best ?? 0;
      const mid = new THREE.Vector3().addVectors(pts[i], pts[i + 1]).multiplyScalar(0.5);
      const t = labelMesh(L.label, { font: 23, weight: 700, color: L.color, bg: th.pill, pad: 6, radius: 7, maxW: 190, border: L.color }, 1300);
      const rec = billboard(grp, t.mesh, mid, 0.17, 0);
      labelMats.push(t.mat);
    }
    const layers = new Set([NODE[L.from].layer, NODE[L.to].layer]);
    linkRec[L.id] = { group: grp, mats, labelMats, layers };
    linkGroup.add(grp);
  }
}

// ---------------------------------------------------------------- visibility / focus
function applyVisibility() {
  root.children.forEach(g => { g.visible = !state.hidden.has(g.userData.layer); });
  S.links.forEach(L => {
    const r = linkRec[L.id];
    r.group.visible = ![...r.layers].some(l => state.hidden.has(l)) && (state.vlinks || !L.implicit);
  });
  // node / link labels follow the Labels toggle (layer titles and group tags always stay)
  for (const id in nodeRec) { const r = nodeRec[id]; if (r.label) r.label.obj.visible = state.labels; }
  S.links.forEach(L => linkRec[L.id].labelMats.forEach(m => { m.visible = state.labels; }));
  requestRender();
}

function focusId() { return state.pinned ?? state.hover; }
function applyFocus() {
  const f = focusId();
  const related = new Set();
  const touching = new Set();
  if (f) {
    related.add(f);
    S.links.forEach(L => { if (L.from === f || L.to === f) { related.add(L.from); related.add(L.to); touching.add(L.id); } });
  }
  for (const n of S.nodes) {
    const r = nodeRec[n.id];
    const k = !f || related.has(n.id) ? 1 : 0.2;
    r.mats.forEach(([m, base]) => { m.opacity = base * k; });
    r.ring.visible = n.id === f;
  }
  for (const L of S.links) {
    const r = linkRec[L.id];
    const o = !f ? (L.implicit ? 0.7 : 0.95) : touching.has(L.id) ? 1 : 0.07;
    r.mats.forEach(m => { m.opacity = o; });
    r.labelMats.forEach(m => { m.opacity = !f || touching.has(L.id) ? 1 : 0; });
  }
  requestRender();
}

// ---------------------------------------------------------------- render loop
const _right = new THREE.Vector3(), _up = new THREE.Vector3();
let queued = false;
function requestRender() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(() => { queued = false; renderNow(); });
}
function renderNow() {
  camera.updateMatrixWorld();
  _right.setFromMatrixColumn(camera.matrixWorld, 0);
  _up.setFromMatrixColumn(camera.matrixWorld, 1);
  for (const b of billboards) {
    b.obj.quaternion.copy(camera.quaternion);
    b.obj.position.copy(b.anchor).addScaledVector(_up, b.up).addScaledVector(_right, b.right);
  }
  renderer.render(scene, camera);
}

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  if (!CLEAN && w > 900) camera.setViewOffset(w, h, -150, 0, w, h); else camera.clearViewOffset();
  fitView(true);
}

const target = new THREE.Vector3();
function sceneBox() {
  const top = (S.levels - 1) * LAYER_GAP * state.explode + 2.4;
  return new THREE.Box3(new THREE.Vector3(OX - 3, -0.3, OZ), new THREE.Vector3(OX + W, top, OZ + D + 1));
}
function fitView(keepAngle) {
  const box = sceneBox();
  box.getCenter(target);
  const dir = keepAngle ? camera.position.clone().sub(controls.target).normalize() : ISO_DIR.clone();
  controls.target.copy(target);
  camera.position.copy(target).addScaledVector(dir, 120);
  camera.lookAt(target);
  camera.updateMatrixWorld();
  const inv = camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
  let hx = 0, hy = 0;
  for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) {
    const p = new THREE.Vector3(x, y, z).applyMatrix4(inv);
    hx = Math.max(hx, Math.abs(p.x)); hy = Math.max(hy, Math.abs(p.y));
  }
  const asp = window.innerWidth / window.innerHeight;
  const panelPad = CLEAN ? 1.04 : 1.1;
  const half = 10;
  camera.left = -half * asp; camera.right = half * asp; camera.top = half; camera.bottom = -half;
  camera.zoom = Math.min(half * asp / hx, half / hy) / panelPad;
  camera.updateProjectionMatrix();
  controls.update();
  requestRender();
}

// ---------------------------------------------------------------- interaction
const ray = new THREE.Raycaster();
const ndc = new THREE.Vector2();
const tip = document.getElementById('tip');
let downAt = null;

function pickAt(ev) {
  const r = canvas.getBoundingClientRect();
  ndc.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(ndc, camera);
  const hits = ray.intersectObjects(picks, false);
  for (const h of hits) {
    const id = h.object.userData.nodeId;
    const node = NODE[id];
    if (!state.hidden.has(node.layer)) return node;
  }
  return null;
}
function showTip(node, ev) {
  if (!node) { tip.style.display = 'none'; return; }
  const layer = S.layers[node.layer];
  const conns = S.links.filter(L => L.from === node.id || L.to === node.id).map(L => {
    const out = L.from === node.id; const other = NODE[out ? L.to : L.from];
    const rel = L.implicit ? (L.class === 'storage' ? (out ? 'mounts' : 'mounted by') : (out ? 'runs on' : 'hosts')) : (out ? '→' : '←');
    return `<li>${rel} ${esc(other.label)}${L.label ? ` <span style="color:var(--sub)">(${esc(L.label)})</span>` : ''}</li>`;
  });
  tip.innerHTML = `<b>${esc(node.label)}</b><div class="meta">${esc(node.kind)} · ${esc(layer.label)}</div>` +
    (node.note ? `<div>${esc(node.note)}</div>` : '') + (conns.length ? `<ul>${conns.join('')}</ul>` : '');
  tip.style.display = 'block';
  const pad = 16, w = tip.offsetWidth, h = tip.offsetHeight;
  tip.style.left = Math.min(ev.clientX + pad, window.innerWidth - w - 8) + 'px';
  tip.style.top = Math.min(ev.clientY + pad, window.innerHeight - h - 8) + 'px';
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

canvas.addEventListener('pointermove', ev => {
  if (ev.buttons) { tip.style.display = 'none'; return; }
  const n = pickAt(ev);
  const id = n ? n.id : null;
  canvas.style.cursor = n ? 'pointer' : 'default';
  if (id !== state.hover) { state.hover = id; applyFocus(); }
  showTip(n, ev);
});
canvas.addEventListener('pointerleave', () => { tip.style.display = 'none'; if (state.hover) { state.hover = null; applyFocus(); } });
canvas.addEventListener('pointerdown', ev => { downAt = [ev.clientX, ev.clientY]; });
canvas.addEventListener('pointerup', ev => {
  if (!downAt || Math.hypot(ev.clientX - downAt[0], ev.clientY - downAt[1]) > 4) return;
  const n = pickAt(ev);
  state.pinned = n && state.pinned !== n.id ? n.id : null;
  applyFocus();
});

function exportPNG(scale = 2) {
  const w = canvas.clientWidth, h = canvas.clientHeight, pr = renderer.getPixelRatio();
  renderer.setPixelRatio(scale); renderer.setSize(w, h, false);
  renderNow();
  canvas.toBlob(b => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(b);
    a.download = (S.title || 'diagram').replace(/[^\w.-]+/g, '_') + '.png';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    renderer.setPixelRatio(pr); renderer.setSize(w, h, false); renderNow();
  }, 'image/png');
}

// ---------------------------------------------------------------- UI
function initUI() {
  document.getElementById('title').textContent = S.title;
  document.getElementById('subtitle').textContent = S.subtitle || '';
  const box = document.getElementById('layers');
  [...S.layers].sort((a, b) => b.level - a.level || a.index - b.index).forEach(l => {
    const lab = document.createElement('label');
    lab.className = 'layer';
    lab.innerHTML = `<input type="checkbox" checked><span class="dot" style="background:${l.color}"></span><span>${esc(l.label)}</span>`;
    lab.querySelector('input').addEventListener('change', e => {
      e.target.checked ? state.hidden.delete(l.index) : state.hidden.add(l.index);
      applyVisibility();
    });
    box.appendChild(lab);
  });
  document.getElementById('explode').addEventListener('input', e => {
    state.explode = parseFloat(e.target.value); build(); fitView(true);
  });
  document.getElementById('reset').onclick = () => { state.pinned = null; fitView(false); applyFocus(); };
  document.getElementById('vlinks').onclick = () => { state.vlinks = !state.vlinks; applyVisibility(); };
  document.getElementById('labels').onclick = () => { state.labels = !state.labels; applyVisibility(); };
  document.getElementById('theme').onclick = () => { state.theme = state.theme === 'dark' ? 'light' : 'dark'; build(); };
  document.getElementById('png').onclick = () => exportPNG(2);
  const lg = document.getElementById('legend');
  if (S.legend.length) {
    lg.innerHTML = '<h2 style="margin:0 0 6px;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--sub)">Links</h2>' +
      S.legend.map(x => `<div class="item"><span class="swatch ${x.dashed ? 'dashed' : ''}" style="border-color:${x.color}"></span>${esc(x.class)}</div>`).join('');
  } else lg.style.display = 'none';
  if (S.warnings.length) document.getElementById('warn').textContent = '⚠ ' + S.warnings.join('\n⚠ ');
}

// ---------------------------------------------------------------- boot
window.addEventListener('resize', resize);
window.exportPNG = exportPNG;
(async () => {
  await prepareIcons();
  initUI();
  build();
  resize();
  fitView(false);
  renderNow();
  document.body.dataset.ready = '1';
})();
