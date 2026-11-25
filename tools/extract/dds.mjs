// Dekoder DDS (BC1, BC3, BC4, BC5, BC7, RGBA8) -> RGBA + zapis PNG. Bez zależności (Node: fs, zlib).
import fs from "node:fs";
import zlib from "node:zlib";

// ---------------- BC7 tablice (specyfikacja BPTC) ----------------
const P2 = [0xCCCC, 0x8888, 0xEEEE, 0xECC8, 0xC880, 0xFEEC, 0xFEC8, 0xEC80, 0xC800, 0xFFEC, 0xFE80, 0xE800, 0xFFE8, 0xFF00, 0xFFF0, 0xF000,
  0xF710, 0x008E, 0x7100, 0x08CE, 0x008C, 0x7310, 0x3100, 0x8CCE, 0x088C, 0x3110, 0x6666, 0x366C, 0x17E8, 0x0FF0, 0x718E, 0x399C,
  0xAAAA, 0xF0F0, 0x5A5A, 0x33CC, 0x3C3C, 0x55AA, 0x9696, 0xA55A, 0x73CE, 0x13C8, 0x324C, 0x3BDC, 0x6996, 0xC33C, 0x9966, 0x0660,
  0x0272, 0x04E4, 0x4E40, 0x2720, 0xC936, 0x936C, 0x39C6, 0x639C, 0x9336, 0x9CC6, 0x817E, 0xE718, 0xCCF0, 0x0FCC, 0x7744, 0xEE22];
const P3 = [
  "0011001102212222", "0001001122112221", "0000200122112211", "0222002200110111", "0000000011221122", "0011001100220022", "0022002211111111", "0011001122112211",
  "0000000011112222", "0000111111112222", "0000111122222222", "0012001200120012", "0112011201120112", "0122012201220122", "0011011211221222", "0011200122002220",
  "0001001101121122", "0111001120012200", "0000112211221122", "0022002200221111", "0111011102220222", "0001000122212221", "0000001101220122", "0000110022102210",
  "0122012200110000", "0012001211222222", "0110122112210110", "0000011012211221", "0022110211020022", "0110011020022222", "0011012201220011", "0000200022112221",
  "0000000211221222", "0222002200120011", "0011001200220222", "0120012001200120", "0000111122220000", "0120120120120120", "0120201212010120", "0011220011220011",
  "0011112222000011", "0101010122222222", "0000000021212121", "0022112200221122", "0022001100220011", "0220122102201221", "0101222222220101", "0000212121212121",
  "0101010101012222", "0222011102220111", "0002111200021112", "0000211221122112", "0222011101110222", "0002111211120002", "0110011001102222", "0000000021122112",
  "0110011022222222", "0022001100110022", "0022112211220022", "0000000000002112", "0002000100020001", "0222122202221222", "0101222222222222", "0111201122012220"]
  .map(s => [...s].map(Number));
const A2 = [15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 8, 2, 2, 8, 8, 15, 2, 8, 2, 2, 8, 8, 2, 2,
  15, 15, 6, 8, 2, 8, 15, 15, 2, 8, 2, 2, 2, 15, 15, 6, 6, 2, 6, 8, 15, 15, 2, 2, 15, 15, 15, 15, 15, 2, 2, 15];
const A3a = [3, 3, 15, 15, 8, 3, 15, 15, 8, 8, 6, 6, 6, 5, 3, 3, 3, 3, 8, 15, 3, 3, 6, 10, 5, 8, 8, 6, 8, 5, 15, 15,
  8, 15, 3, 5, 6, 10, 8, 15, 15, 3, 15, 5, 15, 15, 15, 15, 3, 15, 5, 5, 5, 8, 5, 10, 5, 10, 8, 13, 15, 12, 3, 3];
const A3b = [15, 8, 8, 3, 15, 15, 3, 8, 15, 15, 15, 15, 15, 15, 15, 8, 15, 8, 15, 3, 15, 8, 15, 8, 3, 15, 6, 10, 15, 15, 10, 8,
  15, 3, 15, 10, 10, 8, 9, 10, 6, 15, 8, 15, 3, 6, 6, 8, 15, 3, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 3, 15, 15, 8];
const W = { 2: [0, 21, 43, 64], 3: [0, 9, 18, 27, 37, 46, 55, 64], 4: [0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64] };
// NS, PB, RB, ISB, CB, AB, EPB, SPB, IB, IB2
const MODES = [[3, 4, 0, 0, 4, 0, 1, 0, 3, 0], [2, 6, 0, 0, 6, 0, 0, 1, 3, 0], [3, 6, 0, 0, 5, 0, 0, 0, 2, 0], [2, 6, 0, 0, 7, 0, 1, 0, 2, 0],
  [1, 0, 2, 1, 5, 6, 0, 0, 2, 3], [1, 0, 2, 0, 7, 8, 0, 0, 2, 2], [1, 0, 0, 0, 7, 7, 1, 0, 4, 0], [2, 6, 0, 0, 5, 5, 1, 0, 2, 0]];

export function selfCheck() {
  // kotwice muszą należeć do swojego podzbioru
  for (let p = 0; p < 64; p++) {
    if (!((P2[p] >> A2[p]) & 1)) throw new Error("A2 " + p);
    if (P3[p][A3a[p]] !== 1 || P3[p][A3b[p]] !== 2 || P3[p][0] !== 0) throw new Error("A3 " + p);
  }
}

function bc7Block(src, off, out, ox, oy, stride) {
  let bitPos = 0;
  const bits = n => { let v = 0; for (let i = 0; i < n; i++, bitPos++) v |= ((src[off + (bitPos >> 3)] >> (bitPos & 7)) & 1) << i; return v; };
  let mode = 0; while (mode < 8 && !bits(1)) mode++;
  const px = (i, r, g, b, a) => { const o = ((oy + (i >> 2)) * stride + ox + (i & 3)) * 4; out[o] = r; out[o + 1] = g; out[o + 2] = b; out[o + 3] = a; };
  if (mode === 8) { for (let i = 0; i < 16; i++) px(i, 0, 0, 0, 0); return; }
  const [NS, PB, RB, ISB, CB, AB, EPB, SPB, IB, IB2] = MODES[mode];
  const part = bits(PB), rot = bits(RB), isb = bits(ISB);
  const ne = NS * 2, ep = [];
  for (let e = 0; e < ne; e++) ep.push([0, 0, 0, 255]);
  for (let c = 0; c < 3; c++) for (let e = 0; e < ne; e++) ep[e][c] = bits(CB);
  if (AB) for (let e = 0; e < ne; e++) ep[e][3] = bits(AB);
  let cp = CB, ap = AB;
  if (EPB) { for (let e = 0; e < ne; e++) { const p = bits(1); for (let c = 0; c < 3; c++) ep[e][c] = (ep[e][c] << 1) | p; if (AB) ep[e][3] = (ep[e][3] << 1) | p; } cp++; if (AB) ap++; }
  if (SPB) { for (let s = 0; s < NS; s++) { const p = bits(1); for (const e of [2 * s, 2 * s + 1]) for (let c = 0; c < 3; c++) ep[e][c] = (ep[e][c] << 1) | p; } cp++; }
  const ex = (v, p) => { v <<= 8 - p; return v | (v >> p); };
  for (const e of ep) { for (let c = 0; c < 3; c++) e[c] = ex(e[c], cp); e[3] = AB ? ex(e[3], ap) : 255; }
  const subset = i => NS === 1 ? 0 : NS === 2 ? (P2[part] >> i) & 1 : P3[part][i];
  const anchor = i => i === 0 || (NS === 2 && i === A2[part]) || (NS === 3 && (i === A3a[part] || i === A3b[part]));
  const idx = [], idx2 = [];
  for (let i = 0; i < 16; i++) idx.push(bits(anchor(i) ? IB - 1 : IB));
  if (IB2) for (let i = 0; i < 16; i++) idx2.push(bits(i === 0 ? IB2 - 1 : IB2));
  for (let i = 0; i < 16; i++) {
    const s = subset(i), e0 = ep[2 * s], e1 = ep[2 * s + 1];
    let ci = idx[i], cb = IB, ai = idx[i], ab = IB;
    if (IB2) { if (isb) { ci = idx2[i]; cb = IB2; } else { ai = idx2[i]; ab = IB2; } }
    const wc = W[cb][ci], wa = W[ab][ai];
    const col = [0, 1, 2].map(c => ((64 - wc) * e0[c] + wc * e1[c] + 32) >> 6);
    let a = ((64 - wa) * e0[3] + wa * e1[3] + 32) >> 6;
    if (rot === 1) [a, col[0]] = [col[0], a]; else if (rot === 2) [a, col[1]] = [col[1], a]; else if (rot === 3) [a, col[2]] = [col[2], a];
    px(i, col[0], col[1], col[2], a);
  }
}

// ---------------- BC1/BC3/BC4/BC5 ----------------
function c565(c) { return [((c >> 11) & 31) * 255 / 31 | 0, ((c >> 5) & 63) * 255 / 63 | 0, (c & 31) * 255 / 31 | 0]; }
function bc1Colors(src, off, out, ox, oy, stride, alphaFromBC1) {
  const c0 = src[off] | src[off + 1] << 8, c1 = src[off + 2] | src[off + 3] << 8;
  const a = c565(c0), b = c565(c1), pal = [[...a, 255], [...b, 255]];
  if (c0 > c1 || !alphaFromBC1) { pal.push([0, 1, 2].map(i => (2 * a[i] + b[i]) / 3 | 0).concat(255), [0, 1, 2].map(i => (a[i] + 2 * b[i]) / 3 | 0).concat(255)); }
  else { pal.push([0, 1, 2].map(i => (a[i] + b[i]) / 2 | 0).concat(255), [0, 0, 0, 0]); }
  for (let i = 0; i < 16; i++) { const v = (src[off + 4 + (i >> 2)] >> ((i & 3) * 2)) & 3, o = ((oy + (i >> 2)) * stride + ox + (i & 3)) * 4; out.set(pal[v], o); }
}
function bc4(src, off) {
  const a0 = src[off], a1 = src[off + 1], pal = [a0, a1];
  if (a0 > a1) for (let i = 1; i < 7; i++) pal.push(((7 - i) * a0 + i * a1) / 7 | 0);
  else { for (let i = 1; i < 5; i++) pal.push(((5 - i) * a0 + i * a1) / 5 | 0); pal.push(0, 255); }
  let bitsv = 0n; for (let i = 0; i < 6; i++) bitsv |= BigInt(src[off + 2 + i]) << BigInt(8 * i);
  return Array.from({ length: 16 }, (_, i) => pal[Number((bitsv >> BigInt(3 * i)) & 7n)]);
}

// ---------------- DDS ----------------
export function decodeDDS(buf) {
  if (buf.toString("ascii", 0, 4) !== "DDS ") throw new Error("nie DDS");
  const h = buf.readUInt32LE(12), w = buf.readUInt32LE(16), fourcc = buf.toString("ascii", 84, 88);
  let fmt, dataOff = 128;
  if (fourcc === "DX10") {
    const dx = buf.readUInt32LE(128); dataOff = 148;
    fmt = { 71: "BC1", 72: "BC1", 77: "BC3", 78: "BC3", 80: "BC4", 81: "BC4", 83: "BC5", 84: "BC5", 98: "BC7", 99: "BC7", 28: "RGBA", 29: "RGBA", 87: "BGRA", 91: "BGRA" }[dx];
    if (!fmt) throw new Error("DXGI " + dx);
  } else fmt = { DXT1: "BC1", DXT5: "BC3", ATI1: "BC4", BC4U: "BC4", ATI2: "BC5", BC5U: "BC5" }[fourcc] || (buf.readUInt32LE(88) === 32 ? "BGRA" : null);
  if (!fmt) throw new Error("format " + fourcc);
  const out = new Uint8Array(w * h * 4), src = buf;
  if (fmt === "RGBA" || fmt === "BGRA") {
    for (let i = 0; i < w * h; i++) { const o = dataOff + i * 4; out[i * 4] = src[o + (fmt === "BGRA" ? 2 : 0)]; out[i * 4 + 1] = src[o + 1]; out[i * 4 + 2] = src[o + (fmt === "BGRA" ? 0 : 2)]; out[i * 4 + 3] = src[o + 3]; }
    return { w, h, rgba: out, fmt };
  }
  const bw = Math.max(1, (w + 3) >> 2), bh = Math.max(1, (h + 3) >> 2), bs = fmt === "BC1" || fmt === "BC4" ? 8 : 16;
  const tmpW = bw * 4, tmp = (w % 4 || h % 4) ? new Uint8Array(tmpW * bh * 4 * 4) : out;
  for (let by = 0; by < bh; by++) for (let bx = 0; bx < bw; bx++) {
    const off = dataOff + (by * bw + bx) * bs, ox = bx * 4, oy = by * 4, stride = tmp === out ? w : tmpW;
    if (fmt === "BC7") bc7Block(src, off, tmp, ox, oy, stride);
    else if (fmt === "BC1") bc1Colors(src, off, tmp, ox, oy, stride, true);
    else if (fmt === "BC3") { const a = bc4(src, off); bc1Colors(src, off + 8, tmp, ox, oy, stride, false); for (let i = 0; i < 16; i++) tmp[((oy + (i >> 2)) * stride + ox + (i & 3)) * 4 + 3] = a[i]; }
    else if (fmt === "BC4") { const r = bc4(src, off); for (let i = 0; i < 16; i++) tmp.set([r[i], r[i], r[i], 255], ((oy + (i >> 2)) * stride + ox + (i & 3)) * 4); }
    else if (fmt === "BC5") { const r = bc4(src, off), g = bc4(src, off + 8); for (let i = 0; i < 16; i++) tmp.set([r[i], g[i], 0, 255], ((oy + (i >> 2)) * stride + ox + (i & 3)) * 4); }
  }
  if (tmp !== out) for (let y = 0; y < h; y++) out.set(tmp.subarray(y * tmpW * 4, y * tmpW * 4 + w * 4), y * w * 4);
  return { w, h, rgba: out, fmt };
}

// ---------------- PNG ----------------
const CRC = new Int32Array(256).map((_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; return c; });
function crc32(b) { let c = -1; for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ -1) >>> 0; }
function chunk(type, data) { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type, "ascii"), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc32(td)); return Buffer.concat([len, td, c]); }
export function encodePNG(w, h, rgba, opaque = false) {
  const ch = opaque ? 3 : 4, raw = Buffer.alloc((w * ch + 1) * h);
  for (let y = 0; y < h; y++) { raw[y * (w * ch + 1)] = 0; for (let x = 0; x < w; x++) for (let c = 0; c < ch; c++) raw[y * (w * ch + 1) + 1 + x * ch + c] = rgba[(y * w + x) * 4 + c]; }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = opaque ? 2 : 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw, { level: 6 })), chunk("IEND", Buffer.alloc(0))]);
}

// CLI: node dds.mjs <lista.json>  — [[wejście.dds, wyjście.png], ...]
if (process.argv[1] && process.argv[1].endsWith("dds.mjs") && process.argv[2]) {
  selfCheck();
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  let n = 0;
  for (const [inp, outp] of jobs) {
    const { w, h, rgba } = decodeDDS(fs.readFileSync(inp));
    fs.writeFileSync(outp, encodePNG(w, h, rgba));
    if (++n % 500 === 0) console.log(n + "/" + jobs.length);
  }
  console.log("gotowe", n);
}
