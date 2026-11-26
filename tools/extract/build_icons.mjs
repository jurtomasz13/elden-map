// DDS z assets/cache/{icons,loading} -> PNG w assets/{icons,loading}. Ikony zmniejszane do 256 px, tła do 1280 px.
import fs from "node:fs";
import path from "node:path";
import { decodeDDS, encodePNG } from "./dds.mjs";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..", "..");

function downscale(src, w, h, maxW) {
  let img = src, cw = w, ch = h;
  while (cw > maxW && cw % 2 === 0 && ch % 2 === 0) {
    const nw = cw / 2, nh = ch / 2, out = new Uint8Array(nw * nh * 4);
    for (let y = 0; y < nh; y++) for (let x = 0; x < nw; x++) for (let c = 0; c < 4; c++) {
      const s = (dy, dx) => img[((2 * y + dy) * cw + 2 * x + dx) * 4 + c];
      out[(y * nw + x) * 4 + c] = (s(0, 0) + s(0, 1) + s(1, 0) + s(1, 1) + 2) >> 2;
    }
    img = out; cw = nw; ch = nh;
  }
  return { img, w: cw, h: ch };
}

for (const [kind, maxW, opaque] of [["icons", 256, false], ["loading", 1280, true]]) {
  const src = path.join(ROOT, "assets/cache", kind), dst = path.join(ROOT, "assets", kind);
  fs.mkdirSync(dst, { recursive: true });
  let n = 0;
  for (const f of fs.readdirSync(src).filter(f => f.endsWith(".dds"))) {
    const { w, h, rgba } = decodeDDS(fs.readFileSync(path.join(src, f)));
    const r = downscale(rgba, w, h, maxW);
    fs.writeFileSync(path.join(dst, f.replace(".dds", ".png")), encodePNG(r.w, r.h, r.img, opaque));
    if (++n % 500 === 0) console.log(kind, n);
  }
  console.log(kind, "gotowe:", n);
}

// ikony miejsc na mapie: wycinki z atlasów (extract_icons.py → assets/cache/mapicons) → assets/map/icons/<id>.png
{
  const src = path.join(ROOT, "assets/cache/mapicons"), dst = path.join(ROOT, "assets/map/icons");
  fs.mkdirSync(dst, { recursive: true });
  const layout = JSON.parse(fs.readFileSync(path.join(src, "layout.json"), "utf8")), atlas = {};
  for (const [id, [name, x, y, w, h]] of Object.entries(layout)) {
    const a = atlas[name] ??= decodeDDS(fs.readFileSync(path.join(src, name + ".dds")));
    const out = new Uint8Array(w * h * 4);
    for (let r = 0; r < h; r++) out.set(a.rgba.subarray(((y + r) * a.w + x) * 4, ((y + r) * a.w + x + w) * 4), r * w * 4);
    fs.writeFileSync(path.join(dst, id + ".png"), encodePNG(w, h, out, false));
  }
  console.log("ikony miejsc gotowe:", Object.keys(layout).length);
}
