import fs from "node:fs"; import path from "node:path"; import zlib from "node:zlib";
const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..", "..");   // katalog projektu
import { encodePNG } from "./dds.mjs";
const [map, area, z, c1, c2, out] = process.argv.slice(2);
const root = `${ROOT}/assets/map/${map}/${z}`, scale = 2 ** (6 - +z), W = Math.ceil(10496 / scale);
const img = new Uint8Array(W * W * 4);
function png(p) { const d = fs.readFileSync(p); let i = 8, idat = [], w, h, ct; while (i < d.length) { const n = d.readUInt32BE(i), t = d.toString("ascii", i + 4, i + 8), c = d.subarray(i + 8, i + 8 + n); if (t === "IHDR") { w = c.readUInt32BE(0); h = c.readUInt32BE(4); ct = c[9]; } if (t === "IDAT") idat.push(c); i += 12 + n; } const raw = zlib.inflateSync(Buffer.concat(idat)), ch = ct === 6 ? 4 : 3; return { w, h, ch, raw }; }
for (const tx of fs.readdirSync(root)) for (const f of fs.readdirSync(path.join(root, tx))) { const ty = parseInt(f); const { w, h, ch, raw } = png(path.join(root, tx, f));
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const X = +tx * 256 + x, Y = ty * 256 + y; if (X >= W || Y >= W) continue; const s = y * (w * ch + 1) + 1 + x * ch, d = (Y * W + X) * 4; img[d] = raw[s]; img[d + 1] = raw[s + 1]; img[d + 2] = raw[s + 2]; img[d + 3] = 255; } }
const pts = JSON.parse(fs.readFileSync(`${ROOT}/assets/cache/test/_graces.json`, "utf8"));
for (const [a, X, Z] of pts) { if (a !== +area) continue; const px = Math.round((X - c1 * 256) / scale), py = Math.round((10496 - (Z - c2 * 256)) / scale);
  for (let dy = -3; dy <= 3; dy++) for (let dx = -3; dx <= 3; dx++) { const x = px + dx, y = py + dy; if (x < 0 || y < 0 || x >= W || y >= W) continue; const d = (y * W + x) * 4; img.set(Math.abs(dx) + Math.abs(dy) <= 3 ? [255, 30, 30, 255] : img.subarray(d, d + 4), d); } }
fs.writeFileSync(out, encodePNG(W, W, img)); console.log("ok", W);
