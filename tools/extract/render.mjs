// Programowy renderer modeli (bez GPU) -> PNG z tłem. Dwa przejścia:
//  1) rasteryzacja do bufora (z-bufor): kolor albedo, normalna z mapą normalnych, maska metalu i szorstkość, głębokość;
//  2) oświetlenie: trzy światła (ciepłe główne, chłodne wypełniające, kontra z tyłu), połysk metalu (Blinn-Phong),
//     cień od światła głównego (mapa cieni z filtrowaniem), przyciemnienie zagłębień z bufora głębokości (AO),
//     mapowanie tonów i tło (ciemny gradient z ciepłą poświatą jak przy łasce).
// Mapy normalnych gry (BC7 *_n): R, G = normalna w przestrzeni stycznej, B = maska metalu, A = szorstkość.
// Użycie: node render.mjs <katalog modelu> <wyjście.png> [rozmiar=512] [obrót_Y_stopnie=25] [kadr=full|bust]
import fs from "node:fs";
import path from "node:path";
import { decodeDDS, encodePNG } from "./dds.mjs";

const [dir, outPng, sizeArg = "512", yawArg = "25", crop = "full"] = process.argv.slice(2);
const S = +sizeArg, SS = 3, W = S * SS, H = S * SS;               // supersampling 3x
const model = JSON.parse(fs.readFileSync(path.join(dir, "model.json"), "utf8"));
const yaw = (+yawArg) * Math.PI / 180, pitch = -8 * Math.PI / 180;
const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
const rot = (x, y, z) => { const X = cy * x + sy * z, Z = -sy * x + cy * z; return [X, cp * y - sp * Z, sp * y + cp * Z]; };
const norm = v => { const l = Math.hypot(...v) || 1; return v.map(a => a / l); };

// ramka: obrys obróconych wierzchołków
let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
for (const m of model.meshes) for (let i = 0; i < m.pos.length; i += 3) {
  const [x, y] = rot(m.pos[i], m.pos[i + 1], m.pos[i + 2]);
  minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
}
if (crop === "bust") minY = maxY - (maxY - minY) * 0.5;           // górna połowa postaci
const span = Math.max(maxX - minX, maxY - minY) * 1.08, cx0 = (minX + maxX) / 2, cy0 = (minY + maxY) / 2;
const toScreen = (x, y) => [(x - cx0) / span * W + W / 2, H / 2 - (y - cy0) / span * H];

const texCache = {};
function tex(name) {
  if (!name) return null;
  if (!(name in texCache)) { try { texCache[name] = decodeDDS(fs.readFileSync(path.join(dir, name))); } catch { texCache[name] = null; } }
  return texCache[name];
}
// próbka dwuliniowa (u, v w [0, 1) z powtarzaniem) -> [r, g, b, a] w 0..1
function sample(t, u, v) {
  u = (u - Math.floor(u)) * t.w - .5; v = (v - Math.floor(v)) * t.h - .5;
  const x0 = Math.floor(u), y0 = Math.floor(v), fx = u - x0, fy = v - y0, out = [0, 0, 0, 0];
  for (const [dx, dy, wgt] of [[0, 0, (1 - fx) * (1 - fy)], [1, 0, fx * (1 - fy)], [0, 1, (1 - fx) * fy], [1, 1, fx * fy]]) {
    const xx = ((x0 + dx) % t.w + t.w) % t.w, yy = ((y0 + dy) % t.h + t.h) % t.h, o = (yy * t.w + xx) * 4;
    for (let c = 0; c < 4; c++) out[c] += t.rgba[o + c] * wgt / 255;
  }
  return out;
}
const lin = c => c * c;                                            // sRGB -> liniowo (przybliżenie gamma 2)

// ---------- przejście 1: bufor geometrii ----------
const N = W * H;
const depth = new Float32Array(N).fill(-1e9), alb = new Float32Array(N * 3), nrm = new Float32Array(N * 3);
const vpos = new Float32Array(N * 3), metal = new Float32Array(N), rough = new Float32Array(N).fill(.6), cover = new Uint8Array(N);
const tris = [];                                                   // trójkąty w układzie widoku (do mapy cieni)

for (const m of model.meshes) {
  const t = tex(m.tex), dt = tex(m.detail), st = tex(m.strands), nt = tex(m.normal), P = m.pos, Nm = m.nrm, U = m.uv, T = m.tris, nv = P.length / 3;
  const vp = new Float32Array(nv * 3), sc = new Float32Array(nv * 2), rn = new Float32Array(nv * 3), tg = new Float32Array(nv * 3);
  for (let v = 0; v < nv; v++) {
    const p = rot(P[v * 3], P[v * 3 + 1], P[v * 3 + 2]), s = toScreen(p[0], p[1]);
    vp.set(p, v * 3); sc[v * 2] = s[0]; sc[v * 2 + 1] = s[1];
    if (Nm.length) rn.set(rot(Nm[v * 3], Nm[v * 3 + 1], Nm[v * 3 + 2]), v * 3);
  }
  // styczne z UV (suma po trójkątach), do mapy normalnych
  if (nt && U.length) for (let k = 0; k < T.length; k += 3) {
    const [a, b, c] = [T[k], T[k + 1], T[k + 2]];
    if (a >= nv || b >= nv || c >= nv) continue;
    const e1 = [0, 1, 2].map(i => vp[b * 3 + i] - vp[a * 3 + i]), e2 = [0, 1, 2].map(i => vp[c * 3 + i] - vp[a * 3 + i]);
    const du1 = U[b * 2] - U[a * 2], dv1 = U[b * 2 + 1] - U[a * 2 + 1], du2 = U[c * 2] - U[a * 2], dv2 = U[c * 2 + 1] - U[a * 2 + 1];
    const r = du1 * dv2 - du2 * dv1; if (Math.abs(r) < 1e-12) continue;
    const f = 1 / r;
    for (const i of [a, b, c]) for (let j = 0; j < 3; j++) tg[i * 3 + j] += f * (dv2 * e1[j] - dv1 * e2[j]);
  }
  for (let k = 0; k < T.length; k += 3) {
    const a = T[k], b = T[k + 1], c = T[k + 2];
    if (a >= nv || b >= nv || c >= nv) continue;
    tris.push([vp.slice(a * 3, a * 3 + 3), vp.slice(b * 3, b * 3 + 3), vp.slice(c * 3, c * 3 + 3)]);
    const ax = sc[a * 2], ay = sc[a * 2 + 1], bx = sc[b * 2], by = sc[b * 2 + 1], cx = sc[c * 2], cy2 = sc[c * 2 + 1];
    const area = (bx - ax) * (cy2 - ay) - (by - ay) * (cx - ax);
    if (Math.abs(area) < 1e-6) continue;
    const x0 = Math.max(0, Math.floor(Math.min(ax, bx, cx))), x1 = Math.min(W - 1, Math.ceil(Math.max(ax, bx, cx)));
    const y0 = Math.max(0, Math.floor(Math.min(ay, by, cy2))), y1 = Math.min(H - 1, Math.ceil(Math.max(ay, by, cy2)));
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
      const px = x + .5, py = y + .5;
      const w0 = ((bx - px) * (cy2 - py) - (by - py) * (cx - px)) / area, w1 = ((cx - px) * (ay - py) - (cy2 - py) * (ax - px)) / area, w2 = 1 - w0 - w1;
      if (w0 < 0 || w1 < 0 || w2 < 0) continue;
      const z = w0 * vp[a * 3 + 2] + w1 * vp[b * 3 + 2] + w2 * vp[c * 3 + 2], di = y * W + x;
      if (z <= depth[di]) continue;
      let r = .62, g = .58, bl = .52, mt = 0, rg = .6;
      if (m.color) [r, g, bl] = m.color;                           // jednolity kolor (włosy, skóra bez tekstury)
      const u = U.length ? w0 * U[a * 2] + w1 * U[b * 2] + w2 * U[c * 2] : 0, v = U.length ? w0 * U[a * 2 + 1] + w1 * U[b * 2 + 1] + w2 * U[c * 2 + 1] : 0;
      if (t && U.length && !m.noTex) {
        const s = sample(t, u, v); let al = s[3];
        if (m.alphaOnly) {                                         // włosy: pasma z alfy, kolor z save'a, jaśniejsze końcówki
          if (al < 0.3) continue;
          const sh = 0.75 + 0.35 * al; r = m.color[0] * sh; g = m.color[1] * sh; bl = m.color[2] * sh;
        } else [r, g, bl] = s;
        if (dt) {                                                  // costume: colour palette x grey fabric pattern
          const d = sample(dt, u, v), kk = 1.8 * d[0];
          r = Math.min(1, r * kk); g = Math.min(1, g * kk); bl = Math.min(1, bl * kk); al = Math.min(al, d[3]);
        }
        if (st) {                                                  // fur: hair strands give the shape (alpha) and texture
          const h = sample(st, u, v), kk = 0.55 + 0.7 * (0.3 * h[0] + 0.59 * h[1] + 0.11 * h[2]);
          r *= kk; g *= kk; bl *= kk; al = h[3];
        }
        // przezroczystość z szumem zamiast ostrego progu: po zmniejszeniu kadru krawędzie futra i strzępów są miękkie
        const hash = ((Math.sin(x * 12.9898 + y * 78.233) * 43758.5453) % 1 + 1) % 1;
        if (!m.alphaOnly && al < 0.15 + 0.7 * hash) continue;
        if (m.tint) {                                              // barwienie skóry kolorem z save'a (tekstura twarzy jest neutralna)
          const lum = 0.3 * r + 0.59 * g + 0.11 * bl, kk = 1.9;
          r = Math.min(1, lum * m.tint[0] * kk); g = Math.min(1, lum * m.tint[1] * kk); bl = Math.min(1, lum * m.tint[2] * kk);
        }
      }
      let n = [0, 0, 1];
      if (Nm.length) n = norm([0, 1, 2].map(i => w0 * rn[a * 3 + i] + w1 * rn[b * 3 + i] + w2 * rn[c * 3 + i]));
      if (nt && U.length) {                                        // mapa normalnych w przestrzeni stycznej
        const s = sample(nt, u, v);
        const tx = s[0] * 2 - 1, ty = s[1] * 2 - 1, tz = Math.sqrt(Math.max(0, 1 - tx * tx - ty * ty));
        let tv = [0, 1, 2].map(i => w0 * tg[a * 3 + i] + w1 * tg[b * 3 + i] + w2 * tg[c * 3 + i]);
        const d = tv[0] * n[0] + tv[1] * n[1] + tv[2] * n[2]; tv = norm(tv.map((q, i) => q - n[i] * d));
        const bt = [n[1] * tv[2] - n[2] * tv[1], n[2] * tv[0] - n[0] * tv[2], n[0] * tv[1] - n[1] * tv[0]];
        if (Math.hypot(...tv) > .5) n = norm([0, 1, 2].map(i => tv[i] * tx - bt[i] * ty + n[i] * tz));
        mt = s[2]; rg = s[3];
      }
      if (n[2] < 0) n = n.map(q => -q);                            // tylne ściany dwustronnych tkanin
      depth[di] = z; cover[di] = 1; metal[di] = mt; rough[di] = rg;
      alb.set([lin(r), lin(g), lin(bl)], di * 3); nrm.set(n, di * 3);
      vpos.set([w0 * vp[a * 3] + w1 * vp[b * 3] + w2 * vp[c * 3], w0 * vp[a * 3 + 1] + w1 * vp[b * 3 + 1] + w2 * vp[c * 3 + 1], z], di * 3);
    }
  }
}

// ---------- mapa cieni od światła głównego ----------
const KEY = norm([-0.45, 0.65, 0.62]), FILL = norm([0.7, 0.1, 0.55]), RIM = norm([0.55, 0.35, -0.75]);
const SM = 768, smDepth = new Float32Array(SM * SM).fill(-1e9);
// baza światła: oś z wzdłuż KEY
const kz = KEY, kx = norm([kz[2], 0, -kz[0]]), ky = [kz[1] * kx[2] - kz[2] * kx[1], kz[2] * kx[0] - kz[0] * kx[2], kz[0] * kx[1] - kz[1] * kx[0]];
const toLight = p => [p[0] * kx[0] + p[1] * kx[1] + p[2] * kx[2], p[0] * ky[0] + p[1] * ky[1] + p[2] * ky[2], p[0] * kz[0] + p[1] * kz[1] + p[2] * kz[2]];
let lx0 = 1e9, lx1 = -1e9, ly0 = 1e9, ly1 = -1e9;
const ltris = tris.map(tr => tr.map(toLight));
for (const tr of ltris) for (const p of tr) { lx0 = Math.min(lx0, p[0]); lx1 = Math.max(lx1, p[0]); ly0 = Math.min(ly0, p[1]); ly1 = Math.max(ly1, p[1]); }
const lspan = Math.max(lx1 - lx0, ly1 - ly0) * 1.02 || 1;
const toSM = p => [(p[0] - lx0) / lspan * SM, (p[1] - ly0) / lspan * SM, p[2]];
for (const tr of ltris) {
  const [A, B, C] = tr.map(toSM), area = (B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0]);
  if (Math.abs(area) < 1e-9) continue;
  const x0 = Math.max(0, Math.floor(Math.min(A[0], B[0], C[0]))), x1 = Math.min(SM - 1, Math.ceil(Math.max(A[0], B[0], C[0])));
  const y0 = Math.max(0, Math.floor(Math.min(A[1], B[1], C[1]))), y1 = Math.min(SM - 1, Math.ceil(Math.max(A[1], B[1], C[1])));
  for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
    const px = x + .5, py = y + .5;
    const w0 = ((B[0] - px) * (C[1] - py) - (B[1] - py) * (C[0] - px)) / area, w1 = ((C[0] - px) * (A[1] - py) - (C[1] - py) * (A[0] - px)) / area, w2 = 1 - w0 - w1;
    if (w0 < 0 || w1 < 0 || w2 < 0) continue;
    const z = w0 * A[2] + w1 * B[2] + w2 * C[2], o = y * SM + x;
    if (z > smDepth[o]) smDepth[o] = z;
  }
}
const bias = lspan * 0.004;
function shadow(p) {                                               // 1 = oświetlone, 0 = w cieniu (filtr 5x5)
  const [x, y, z] = toSM(toLight(p)); let lit = 0, n = 0;
  for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
    const xx = Math.min(SM - 1, Math.max(0, Math.floor(x) + dx)), yy = Math.min(SM - 1, Math.max(0, Math.floor(y) + dy));
    lit += z >= smDepth[yy * SM + xx] - bias ? 1 : 0; n++;
  }
  return lit / n;
}

// ---------- AO z bufora głębokości (zagłębienia, styki części) ----------
const pxSize = span / W, aoR = Math.max(4, Math.round(W * 0.018));
const DIRS = [...Array(12).keys()].map(i => [Math.cos(i * Math.PI / 6), Math.sin(i * Math.PI / 6)]);
function ao(x, y) {
  const o = y * W + x, z = depth[o]; let occ = 0;
  for (const [dx, dy] of DIRS) for (const s of [0.35, 0.7, 1]) {
    const xx = Math.round(x + dx * aoR * s), yy = Math.round(y + dy * aoR * s);
    if (xx < 0 || yy < 0 || xx >= W || yy >= H || !cover[yy * W + xx]) continue;
    const dz = depth[yy * W + xx] - z, dist = aoR * s * pxSize;
    if (dz > 0.02 * dist) occ += Math.min(1, dz / (dist * 2)) * (1 - s * 0.3);
  }
  return Math.max(0.35, 1 - occ / (DIRS.length * 2.2));
}

// ---------- przejście 2: oświetlenie ----------
const color = new Float32Array(N * 4), VIEW = [0, 0, 1];
const tone = x => { x *= 1.15; return Math.pow(Math.max(0, (x * (2.51 * x + .03)) / (x * (2.43 * x + .59) + .14)), 1 / 2.2); };   // ACES + gamma
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
  const o = y * W + x; if (!cover[o]) continue;
  const n = [nrm[o * 3], nrm[o * 3 + 1], nrm[o * 3 + 2]], p = [vpos[o * 3], vpos[o * 3 + 1], vpos[o * 3 + 2]];
  const a = [alb[o * 3], alb[o * 3 + 1], alb[o * 3 + 2]], mt = metal[o], gloss = 1 - rough[o];
  const dot = (u, v) => u[0] * v[0] + u[1] * v[1] + u[2] * v[2];
  const sh = shadow(p), occ = ao(x, y);
  const spec = L => { const h = norm([L[0] + VIEW[0], L[1] + VIEW[1], L[2] + VIEW[2]]); return Math.pow(Math.max(0, dot(n, h)), 8 + 90 * gloss) * (0.04 + 0.9 * mt) * (0.4 + gloss); };
  const kd = Math.max(0, dot(n, KEY)) * sh, fd = Math.max(0, dot(n, FILL) * 0.5 + 0.5) ** 2, rd = Math.max(0, dot(n, RIM));
  const sky = 0.5 + 0.5 * n[1];                                     // otoczenie: jaśniej z góry
  const KEYC = [2.3, 1.95, 1.45], FILLC = [0.16, 0.19, 0.27], RIMC = [1.5, 1.25, 0.9], AMB = [0.06 + 0.06 * sky, 0.055 + 0.05 * sky, 0.05 + 0.045 * sky];
  for (let c = 0; c < 3; c++) {
    const diff = a[c] * (1 - mt * 0.6) * (KEYC[c] * kd + FILLC[c] * fd + AMB[c] * 2.2) * occ;
    const metalTint = mt > 0.3 ? a[c] * 1.6 + 0.15 : 1;            // odbicie metalu w jego kolorze
    const sp = (KEYC[c] * spec(KEY) * sh + RIMC[c] * spec(RIM) * 0.6) * metalTint;
    color[o * 4 + c] = tone(diff + sp + RIMC[c] * Math.pow(rd, 3) * 0.55 * occ);
  }
  color[o * 4 + 3] = 1;
}

// kadrowanie po faktycznie narysowanych pikselach (obrys wierzchołków bywa zawyżony przez ukryte meshe)
let ax0 = W, ax1 = -1, ay0 = H, ay1 = -1;
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (cover[y * W + x]) {
  if (x < ax0) ax0 = x; if (x > ax1) ax1 = x; if (y < ay0) ay0 = y; if (y > ay1) ay1 = y;
}
if (ax1 < 0) { ax0 = 0; ax1 = W - 1; ay0 = 0; ay1 = H - 1; }
let side, sx0, sy0;
if (crop === "bust") {
  // górne ~45% sylwetki; środek w poziomie liczony z pikseli tego pasa
  const band = Math.max(8, (ay1 - ay0) * 0.6), by1 = ay0 + band;
  let bx0 = W, bx1 = -1, sum = 0, cnt = 0;
  for (let y = ay0; y < by1; y++) for (let x = 0; x < W; x++) if (cover[y * W + x]) { if (x < bx0) bx0 = x; if (x > bx1) bx1 = x; sum += x; cnt++; }
  side = Math.max(band, Math.min(bx1 - bx0, band * 1.15)) * 1.15;
  const cxm = cnt ? sum / cnt : (ax0 + ax1) / 2;
  sx0 = cxm - side / 2; sy0 = ay0 - side * 0.06;
} else {
  side = Math.max(ax1 - ax0, ay1 - ay0) * 1.06;
  sx0 = (ax0 + ax1) / 2 - side / 2; sy0 = (ay0 + ay1) / 2 - side / 2;
}
// tło: ciemny popiół z ciepłą poświatą za głową, winieta i drobne ziarno
function background(x, y) {
  const u = x / S - .5, v = y / S - .38, d = Math.hypot(u * 1.1, v), glow = Math.exp(-d * d * 7);
  const vig = 1 - Math.min(1, Math.hypot(x / S - .5, y / S - .5) * 1.25) ** 2 * .55;
  const grain = (Math.sin(x * 12.9898 + y * 78.233) * 43758.5453 % 1) * .015;
  return [(0.055 + 0.30 * glow) * vig + grain, (0.047 + 0.22 * glow) * vig + grain, (0.038 + 0.11 * glow) * vig + grain];
}
// próbkowanie obszarowe kadru do S×S (antyaliasing), postać na tle
const out = new Uint8Array(S * S * 4), k = side / S;
for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
  let r = 0, g = 0, b = 0, a = 0, n = 0;
  const X0 = sx0 + x * k, Y0 = sy0 + y * k;
  for (let yy = Math.floor(Y0); yy < Math.ceil(Y0 + k); yy++) for (let xx = Math.floor(X0); xx < Math.ceil(X0 + k); xx++) {
    n++;
    if (xx < 0 || yy < 0 || xx >= W || yy >= H) continue;
    const o = (yy * W + xx) * 4, al = color[o + 3]; r += color[o] * al; g += color[o + 1] * al; b += color[o + 2] * al; a += al;
  }
  n = n || 1; const cov = a / n, bg = background(x, y), o = (y * S + x) * 4;
  out[o] = Math.round(255 * Math.min(1, (a ? r / a : 0) * cov + bg[0] * (1 - cov)));
  out[o + 1] = Math.round(255 * Math.min(1, (a ? g / a : 0) * cov + bg[1] * (1 - cov)));
  out[o + 2] = Math.round(255 * Math.min(1, (a ? b / a : 0) * cov + bg[2] * (1 - cov)));
  out[o + 3] = 255;
}
fs.mkdirSync(path.dirname(outPng), { recursive: true });
fs.writeFileSync(outPng, encodePNG(S, S, out));
console.log("zapisano", outPng);
