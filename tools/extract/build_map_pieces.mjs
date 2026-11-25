// Maski fragmentów mapy: dla każdej mapy obraz 41·32 px (1 piksel = 8×8 px mapy), w którym kanały R,G,B niosą bity
// fragmentów (0–7, 8–15, 16–23) pokrywających dane miejsce. Strona w trybie „Mój postęp” zakrywa pustą fakturą
// z gry miejsca, których żaden zebrany fragment nie odsłania — jak mapa w grze.
// Wejście: assets/cache/map/pieces/manifest.json (extract_map_pieces.py). Wyjście: assets/map/<M>/pieces.png, assets/map/blank.png
import fs from "node:fs";
import path from "node:path";
import { decodeDDS, encodePNG } from "./dds.mjs";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..", "..");
const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "assets/cache/map/pieces/manifest.json"), "utf8"));
const GRID = 41, T = 256, B = 8, S = T / B;          // kafel 256 px -> 32 piksele maski
const DIFF = 60, SHARE = 0.2;                        // piksel różny: suma |ΔRGB| > 60; blok należy do fragmentu: > 20% różnych
const cache = new Map();
const rgba = f => { if (!cache.has(f)) { if (cache.size > 64) cache.clear(); cache.set(f, decodeDDS(fs.readFileSync(f)).rgba); } return cache.get(f); };

for (const [map, cells] of Object.entries(manifest)) {
  if (map.startsWith("_")) continue;
  const W = GRID * S, img = new Uint8Array(W * W * 4);
  for (let i = 3; i < img.length; i += 4) img[i] = 255;
  for (const c of cells) {
    const oy = (GRID - 1 - c.y) * S, ox = c.x * S;      // siatka gry ma y rosnące w górę
    for (const [bit, [withF, withoutF]] of Object.entries(c.pairs)) {
      const a = rgba(withF), b = rgba(withoutF), ch = Math.floor(bit / 8), mask = 1 << (bit % 8);
      for (let by = 0; by < S; by++) for (let bx = 0; bx < S; bx++) {
        let diff = 0;
        for (let r = 0; r < B; r++) for (let q = 0; q < B; q++) {
          const s = ((by * B + r) * T + bx * B + q) * 4;
          if (Math.abs(a[s] - b[s]) + Math.abs(a[s + 1] - b[s + 1]) + Math.abs(a[s + 2] - b[s + 2]) > DIFF) diff++;
        }
        if (diff > SHARE * B * B) img[((oy + by) * W + ox + bx) * 4 + ch] |= mask;
      }
    }
  }
  fs.mkdirSync(path.join(ROOT, "assets/map", map), { recursive: true });
  fs.writeFileSync(path.join(ROOT, "assets/map", map, "pieces.png"), encodePNG(W, W, img, true));
  console.log(map, "maska fragmentów", W + "px,", cells.length, "kafli");
}
if (manifest._blank) {
  const { w, h, rgba: px } = decodeDDS(fs.readFileSync(manifest._blank));
  fs.writeFileSync(path.join(ROOT, "assets/map/blank.png"), encodePNG(w, h, px, true));
  console.log("faktura nieodkrytej mapy: assets/map/blank.png");
}
