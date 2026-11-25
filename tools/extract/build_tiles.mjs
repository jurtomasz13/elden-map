// Piramida kafli pod Leaflet (CRS.Simple) z kafli L0 gry.
// Wejście: assets/cache/map/manifest.json (extract_map.py). Wyjście: assets/map/<M>/<z>/<x>/<y>.png + meta.json
// Siatka gry ma y rosnące w górę — odwracamy, żeby y=0 był na górze (jak w Leaflet).
import fs from "node:fs";
import path from "node:path";
import { decodeDDS, encodePNG } from "./dds.mjs";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..", "..");
const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "assets/cache/map/manifest.json"), "utf8"));
const T = 256, only = process.argv[2];
const meta = {};

for (const [map, tiles] of Object.entries(manifest)) {
  if (only && map !== only) continue;
  const gridN = Math.max(41, ...tiles.map(t => Math.max(t.x, t.y) + 1)); // L0 ma siatkę 41x41 we wszystkich mapach
  const zMax = Math.ceil(Math.log2(gridN));                            // 41 -> 6 (64 kafle)
  const size = gridN * T;
  let img = new Uint8Array(size * size * 3);                           // RGB, tło = czerń
  for (const t of tiles) {
    const { rgba } = decodeDDS(fs.readFileSync(t.file));
    const oy = (gridN - 1 - t.y) * T, ox = t.x * T;
    for (let r = 0; r < T; r++) for (let c = 0; c < T; c++) {
      const s = (r * T + c) * 4, d = ((oy + r) * size + ox + c) * 3;
      img[d] = rgba[s]; img[d + 1] = rgba[s + 1]; img[d + 2] = rgba[s + 2];
    }
  }
  console.log(map, "złożono", size + "px");
  let w = size, count = 0;
  for (let z = zMax; z >= 0; z--) {
    const n = Math.ceil(w / T);
    for (let ty = 0; ty < n; ty++) for (let tx = 0; tx < n; tx++) {
      const tile = new Uint8Array(T * T * 4);
      let any = false;
      for (let r = 0; r < T; r++) for (let c = 0; c < T; c++) {
        const sy = ty * T + r, sx = tx * T + c, d = (r * T + c) * 4;
        if (sy < w && sx < w) { const s = (sy * w + sx) * 3; tile[d] = img[s]; tile[d + 1] = img[s + 1]; tile[d + 2] = img[s + 2]; tile[d + 3] = 255; any = true; }
      }
      if (!any) continue;
      const dir = path.join(ROOT, "assets/map", map, String(z), String(tx));
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, ty + ".png"), encodePNG(T, T, tile));
      count++;
    }
    if (z > 0) { // zmniejszenie 2x (średnia z 2x2)
      const nw = Math.ceil(w / 2), next = new Uint8Array(nw * nw * 3);
      for (let y = 0; y < nw; y++) for (let x = 0; x < nw; x++) for (let ch = 0; ch < 3; ch++) {
        let sum = 0, k = 0;
        for (let dy = 0; dy < 2; dy++) for (let dx = 0; dx < 2; dx++) { const sy = 2 * y + dy, sx = 2 * x + dx; if (sy < w && sx < w) { sum += img[(sy * w + sx) * 3 + ch]; k++; } }
        next[(y * nw + x) * 3 + ch] = Math.round(sum / k);
      }
      img = next; w = nw;
    }
  }
  meta[map] = { gridN, tileSize: T, zMax, sizePx: size, tiles: count, yFlipped: true };
  console.log(map, "zapisano", count, "kafli PNG, zoom 0 -", zMax);
}
const metaPath = path.join(ROOT, "assets/map/meta.json");
const old = fs.existsSync(metaPath) ? JSON.parse(fs.readFileSync(metaPath, "utf8")) : {};
fs.writeFileSync(metaPath, JSON.stringify({ ...old, ...meta }, null, 2));
