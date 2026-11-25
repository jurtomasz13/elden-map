import fs from "node:fs"; import path from "node:path"; import zlib from "node:zlib";
const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..", "..");   // katalog projektu
const [map, area, seaX, seaY] = process.argv.slice(2), z = 4, scale = 4, W = 2624;
const root = `${ROOT}/assets/map/${map}/${z}`, img = new Uint8Array(W * W * 3);
function png(p) { const d = fs.readFileSync(p); let i = 8, idat = [], w, h, ct; while (i < d.length) { const n = d.readUInt32BE(i), t = d.toString("ascii", i + 4, i + 8), c = d.subarray(i + 8, i + 8 + n); if (t === "IHDR") { w = c.readUInt32BE(0); h = c.readUInt32BE(4); ct = c[9]; } if (t === "IDAT") idat.push(c); i += 12 + n; } return { w, h, ch: ct === 6 ? 4 : 3, raw: zlib.inflateSync(Buffer.concat(idat)) }; }
for (const tx of fs.readdirSync(root)) for (const f of fs.readdirSync(path.join(root, tx))) { const ty = parseInt(f), { w, h, ch, raw } = png(path.join(root, tx, f));
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const X = +tx * 256 + x, Y = ty * 256 + y; if (X < W && Y < W) { const s = y * (w * ch + 1) + 1 + x * ch, d = (Y * W + X) * 3; img[d] = raw[s]; img[d + 1] = raw[s + 1]; img[d + 2] = raw[s + 2]; } } }
const px = (x, y) => { const d = (y * W + x) * 3; return [img[d], img[d + 1], img[d + 2]]; };
// kolor morza = średnia z okna 9x9 wokół punktu podanego w pikselach z=4
let sea = [0, 0, 0]; for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) { const p = px(+seaX + dx, +seaY + dy); sea = sea.map((v, i) => v + p[i] / 81); }
const isSea = (x, y) => { let n = 0; for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) { const p = px(x + dx, y + dy); if (Math.hypot(p[0] - sea[0], p[1] - sea[1], p[2] - sea[2]) < 28) n++; } return n > 12; };
const pts = JSON.parse(fs.readFileSync(`${ROOT}/assets/cache/test/_graces.json`, "utf8")).filter(p => p[0] === +area);
const res = [];
for (let ox = 29 * 256 - 512; ox <= 29 * 256 + 512; ox += 32) for (let oz = 24 * 256 - 512; oz <= 24 * 256 + 512; oz += 32) {
  let bad = 0; for (const [, X, Z] of pts) { const x = Math.round((X - ox) / scale), y = Math.round((10496 - (Z - oz)) / scale); if (x < 3 || y < 3 || x >= W - 3 || y >= W - 3 || isSea(x, y)) bad++; }
  res.push([bad, ox, oz]);
}
res.sort((a, b) => a[0] - b[0]);
console.log(map, "łask", pts.length, "morze", sea.map(Math.round), "najlepsze (złe, offX, offZ):", res.slice(0, 8).map(r => r.join("/")).join("  "));
