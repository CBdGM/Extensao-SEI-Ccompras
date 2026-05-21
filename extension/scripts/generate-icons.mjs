/**
 * Generates minimal valid PNG icons for the extension.
 * No external dependencies — uses only Node built-ins (zlib, fs).
 * Run: node scripts/generate-icons.mjs
 */
import { deflateSync } from "zlib";
import { writeFileSync, mkdirSync } from "fs";
import { fileURLToPath } from "url";
import { resolve, dirname } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const iconsDir = resolve(__dirname, "../public/icons");

// ── CRC-32 (required by PNG spec) ──────────────────────────────────────────
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[i] = c;
  }
  return t;
})();

function crc32(buf) {
  let crc = 0xffffffff;
  for (const b of buf) crc = CRC_TABLE[(crc ^ b) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function makeChunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const typeBuf = Buffer.from(type, "ascii");
  const crcBuf = Buffer.alloc(4);
  crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])));
  return Buffer.concat([len, typeBuf, data, crcBuf]);
}

// ── PNG builder ──────────────────────────────────────────────────────────
function createSolidPNG(size, { r, g, b, a = 255 }) {
  const PNG_SIG = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

  // IHDR: width, height, bit-depth=8, color-type=6 (RGBA), compress=0, filter=0, interlace=0
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8;  // bit depth
  ihdr[9] = 6;  // RGBA
  // bytes 10-12 remain 0

  // Raw scanlines: 1 filter byte + 4 bytes per pixel
  const rowStride = 1 + size * 4;
  const raw = Buffer.alloc(size * rowStride);
  for (let y = 0; y < size; y++) {
    raw[y * rowStride] = 0; // filter = None
    for (let x = 0; x < size; x++) {
      const i = y * rowStride + 1 + x * 4;
      raw[i]     = r;
      raw[i + 1] = g;
      raw[i + 2] = b;
      raw[i + 3] = a;
    }
  }

  return Buffer.concat([
    PNG_SIG,
    makeChunk("IHDR", ihdr),
    makeChunk("IDAT", deflateSync(raw)),
    makeChunk("IEND", Buffer.alloc(0)),
  ]);
}

// ── Draw a simple "C" letter icon ────────────────────────────────────────
// For each size we paint bg #1a56db and a white "C" shape via pixel offsets.
function createIconPNG(size) {
  // Background: #1a56db
  const bg = { r: 26, g: 86, b: 219, a: 255 };
  const fg = { r: 255, g: 255, b: 255, a: 255 }; // white

  const rowStride = 1 + size * 4;
  const raw = Buffer.alloc(size * rowStride);

  // Fill background
  for (let y = 0; y < size; y++) {
    raw[y * rowStride] = 0;
    for (let x = 0; x < size; x++) {
      const i = y * rowStride + 1 + x * 4;
      raw[i]     = bg.r;
      raw[i + 1] = bg.g;
      raw[i + 2] = bg.b;
      raw[i + 3] = bg.a;
    }
  }

  // Draw a simple rounded rectangle border (white ring) as the icon shape
  const pad = Math.max(1, Math.round(size * 0.1));
  const thick = Math.max(1, Math.round(size * 0.12));

  function setPixel(x, y) {
    if (x < 0 || x >= size || y < 0 || y >= size) return;
    const i = y * rowStride + 1 + x * 4;
    raw[i]     = fg.r;
    raw[i + 1] = fg.g;
    raw[i + 2] = fg.b;
    raw[i + 3] = fg.a;
  }

  // Top bar
  for (let x = pad; x < size - pad; x++)
    for (let t = 0; t < thick; t++) setPixel(x, pad + t);

  // Bottom bar
  for (let x = pad; x < size - pad; x++)
    for (let t = 0; t < thick; t++) setPixel(x, size - pad - t - 1);

  // Left bar (full height)
  for (let y = pad; y < size - pad; y++)
    for (let t = 0; t < thick; t++) setPixel(pad + t, y);

  // Right bar (only top and bottom thirds — makes it look like a "C")
  const third = Math.round((size - 2 * pad) / 3);
  for (let y = pad; y < pad + third; y++)
    for (let t = 0; t < thick; t++) setPixel(size - pad - t - 1, y);
  for (let y = size - pad - third; y < size - pad; y++)
    for (let t = 0; t < thick; t++) setPixel(size - pad - t - 1, y);

  const PNG_SIG = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8;
  ihdr[9] = 6; // RGBA

  return Buffer.concat([
    PNG_SIG,
    makeChunk("IHDR", ihdr),
    makeChunk("IDAT", deflateSync(raw)),
    makeChunk("IEND", Buffer.alloc(0)),
  ]);
}

// ── Generate ─────────────────────────────────────────────────────────────
mkdirSync(iconsDir, { recursive: true });

for (const size of [16, 48, 128]) {
  const out = resolve(iconsDir, `icon${size}.png`);
  writeFileSync(out, createIconPNG(size));
  console.log(`✓ icon${size}.png  (${size}×${size}px)`);
}

console.log("Icons created in public/icons/");
