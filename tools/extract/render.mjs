// Programowy renderer modeli (bez GPU): z-bufor, tekstury albedo, oświetlenie, przezroczyste tło -> PNG.
// Użycie: node render.mjs <katalog modelu> <wyjście.png> [rozmiar=512] [obrót_Y_stopnie=25] [kadr=full|bust]
import fs from "node:fs";
import path from "node:path";
import { decodeDDS, encodePNG } from "./dds.mjs";

const [dir, outPng, sizeArg = "512", yawArg = "25", crop = "full"] = process.argv.slice(2);
const S = +sizeArg, SS = 2, W = S * SS, H = S * SS;               // supersampling 2x
const model = JSON.parse(fs.readFileSync(path.join(dir, "model.json"), "utf8"));
const yaw = (+yawArg) * Math.PI / 180, pitch = -8 * Math.PI / 180;
const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
const rot = (x, y, z) => { const X = cy * x + sy * z, Z = -sy * x + cy * z; return [X, cp * y - sp * Z, sp * y + cp * Z]; };

// ramka: obrys obróconych wierzchołków
let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
for (const m of model.meshes) for (let i = 0; i < m.pos.length; i += 3) {
  const [x, y] = rot(m.pos[i], m.pos[i + 1], m.pos[i + 2]);
  minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
}
if (crop === "bust") minY = maxY - (maxY - minY) * 0.5;           // górna połowa postaci
const span = Math.max(maxX - minX, maxY - minY) * 1.08, cx0 = (minX + maxX) / 2, cy0 = (minY + maxY) / 2;
const toScreen = (x, y) => [(x - cx0) / span * W + W / 2, H / 2 - (y - cy0) / span * H];

const color = new Float32Array(W * H * 4), depth = new Float32Array(W * H).fill(-1e9);
const L1 = norm([-0.4, 0.6, 0.7]), L2 = norm([0.7, 0.2, -0.6]);
function norm(v) { const l = Math.hypot(...v) || 1; return v.map(a => a / l); }
const texCache = {};
function tex(name) {
  if (!name) return null;
  if (!(name in texCache)) { try { const t = decodeDDS(fs.readFileSync(path.join(dir, name))); texCache[name] = t; } catch { texCache[name] = null; } }
  return texCache[name];
}

for (const m of model.meshes) {
  const t = tex(m.tex), P = m.pos, N = m.nrm, U = m.uv, T = m.tris, nv = P.length / 3;
  const sp2 = new Float32Array(nv * 3), rn = new Float32Array(nv * 3);
  for (let v = 0; v < nv; v++) {
    const [x, y, z] = rot(P[v * 3], P[v * 3 + 1], P[v * 3 + 2]); const [sx, sy2] = toScreen(x, y);
    sp2[v * 3] = sx; sp2[v * 3 + 1] = sy2; sp2[v * 3 + 2] = z;
    if (N.length) { const n = rot(N[v * 3], N[v * 3 + 1], N[v * 3 + 2]); rn[v * 3] = n[0]; rn[v * 3 + 1] = n[1]; rn[v * 3 + 2] = n[2]; }
  }
  for (let k = 0; k < T.length; k += 3) {
    const a = T[k], b = T[k + 1], c = T[k + 2];
    if (a >= nv || b >= nv || c >= nv) continue;
    const ax = sp2[a * 3], ay = sp2[a * 3 + 1], bx = sp2[b * 3], by = sp2[b * 3 + 1], cx = sp2[c * 3], cy2 = sp2[c * 3 + 1];
    const area = (bx - ax) * (cy2 - ay) - (by - ay) * (cx - ax);
    if (Math.abs(area) < 1e-6) continue;
    const x0 = Math.max(0, Math.floor(Math.min(ax, bx, cx))), x1 = Math.min(W - 1, Math.ceil(Math.max(ax, bx, cx)));
    const y0 = Math.max(0, Math.floor(Math.min(ay, by, cy2))), y1 = Math.min(H - 1, Math.ceil(Math.max(ay, by, cy2)));
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
      const px = x + .5, py = y + .5;
      const w0 = ((bx - px) * (cy2 - py) - (by - py) * (cx - px)) / area, w1 = ((cx - px) * (ay - py) - (cy2 - py) * (ax - px)) / area, w2 = 1 - w0 - w1;
      if (w0 < 0 || w1 < 0 || w2 < 0) continue;
      const z = w0 * sp2[a * 3 + 2] + w1 * sp2[b * 3 + 2] + w2 * sp2[c * 3 + 2], di = y * W + x;
      if (z <= depth[di]) continue;
      let r = .62, g = .58, bl = .52, al = 1;
      if (m.color) { r = m.color[0]; g = m.color[1]; bl = m.color[2]; }        // jednolity kolor (włosy, skóra bez tekstury)
      if (t && U.length && !m.noTex) {
        let u = w0 * U[a * 2] + w1 * U[b * 2] + w2 * U[c * 2], v = w0 * U[a * 2 + 1] + w1 * U[b * 2 + 1] + w2 * U[c * 2 + 1];
        u -= Math.floor(u); v -= Math.floor(v);
        const tx = Math.min(t.w - 1, (u * t.w) | 0), ty = Math.min(t.h - 1, (v * t.h) | 0), ti = (ty * t.w + tx) * 4;
        al = t.rgba[ti + 3] / 255;
        if (m.alphaOnly) {                                                // włosy: pasma z alfy, kolor z save'a, jaśniejsze końcówki
          if (al < 0.3) continue;
          const sh = 0.75 + 0.35 * al; r = m.color[0] * sh; g = m.color[1] * sh; bl = m.color[2] * sh;
        } else { r = t.rgba[ti] / 255; g = t.rgba[ti + 1] / 255; bl = t.rgba[ti + 2] / 255; }
        if (al < 0.4 && !m.alphaOnly) continue;                                           // alpha test (włosy, tkaniny)
        if (m.tint) {                                                     // barwienie skóry kolorem z save'a (tekstura twarzy jest neutralna)
          const lum = 0.3 * r + 0.59 * g + 0.11 * bl, k = 1.9;
          r = Math.min(1, lum * m.tint[0] * k); g = Math.min(1, lum * m.tint[1] * k); bl = Math.min(1, lum * m.tint[2] * k);
        }
      }
      let nx = 0, ny = 0, nz = 1;
      if (N.length) { nx = w0 * rn[a * 3] + w1 * rn[b * 3] + w2 * rn[c * 3]; ny = w0 * rn[a * 3 + 1] + w1 * rn[b * 3 + 1] + w2 * rn[c * 3 + 1]; nz = w0 * rn[a * 3 + 2] + w1 * rn[b * 3 + 2] + w2 * rn[c * 3 + 2];
        const l = Math.hypot(nx, ny, nz) || 1; nx /= l; ny /= l; nz /= l; if (nz < 0) { nx = -nx; ny = -ny; nz = -nz; } }
      const d1 = Math.max(0, nx * L1[0] + ny * L1[1] + nz * L1[2]), d2 = Math.max(0, nx * L2[0] + ny * L2[1] + nz * L2[2]);
      const lit = 0.38 + 0.85 * d1, rim = 0.35 * d2;
      depth[di] = z; const o = di * 4;
      color[o] = Math.min(1, r * lit + rim * .95); color[o + 1] = Math.min(1, g * lit + rim * .85); color[o + 2] = Math.min(1, bl * lit + rim * .6); color[o + 3] = 1;
    }
  }
}
// kadrowanie po faktycznie narysowanych pikselach (obrys wierzchołków bywa zawyżony przez ukryte meshe)
let ax0 = W, ax1 = -1, ay0 = H, ay1 = -1;
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (color[(y * W + x) * 4 + 3]) {
  if (x < ax0) ax0 = x; if (x > ax1) ax1 = x; if (y < ay0) ay0 = y; if (y > ay1) ay1 = y;
}
if (ax1 < 0) { ax0 = 0; ax1 = W - 1; ay0 = 0; ay1 = H - 1; }
let side, sx0, sy0;
if (crop === "bust") {
  // górne ~45% sylwetki; środek w poziomie liczony z pikseli tego pasa
  const band = Math.max(8, (ay1 - ay0) * 0.6), by1 = ay0 + band;
  let bx0 = W, bx1 = -1, sum = 0, cnt = 0;
  for (let y = ay0; y < by1; y++) for (let x = 0; x < W; x++) if (color[(y * W + x) * 4 + 3]) { if (x < bx0) bx0 = x; if (x > bx1) bx1 = x; sum += x; cnt++; }
  side = Math.max(band, Math.min(bx1 - bx0, band * 1.15)) * 1.15;
  const cxm = cnt ? sum / cnt : (ax0 + ax1) / 2;
  sx0 = cxm - side / 2; sy0 = ay0 - side * 0.06;
} else {
  side = Math.max(ax1 - ax0, ay1 - ay0) * 1.06;
  sx0 = (ax0 + ax1) / 2 - side / 2; sy0 = (ay0 + ay1) / 2 - side / 2;
}
// próbkowanie obszarowe kadru do S×S (antyaliasing) i zapis
const out = new Uint8Array(S * S * 4), k = side / S;
for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
  let r = 0, g = 0, b = 0, a = 0, n = 0;
  const X0 = sx0 + x * k, Y0 = sy0 + y * k;
  for (let yy = Math.floor(Y0); yy < Math.ceil(Y0 + k); yy++) for (let xx = Math.floor(X0); xx < Math.ceil(X0 + k); xx++) {
    n++;
    if (xx < 0 || yy < 0 || xx >= W || yy >= H) continue;
    const o = (yy * W + xx) * 4, al = color[o + 3]; r += color[o] * al; g += color[o + 1] * al; b += color[o + 2] * al; a += al;
  }
  const o = (y * S + x) * 4; n = n || 1;
  out[o] = a ? Math.round(r / a * 255) : 0; out[o + 1] = a ? Math.round(g / a * 255) : 0; out[o + 2] = a ? Math.round(b / a * 255) : 0; out[o + 3] = Math.round(a / n * 255);
}
fs.mkdirSync(path.dirname(outPng), { recursive: true });
fs.writeFileSync(outPng, encodePNG(S, S, out));
console.log("zapisano", outPng);
