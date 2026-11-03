const EDGE = 384;
const HEADER_BYTES = 256 * 1024;
let previewQueue = Promise.resolve();

/** Read only container metadata: never decode the full image to discover its dimensions. */
export function photoPreviewDimensions(bytes: Uint8Array): [number, number] | null {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const text = (start: number, end: number) => String.fromCharCode(...bytes.subarray(start, end));
  let width = 0;
  let height = 0;
  let orientation = 1;
  try {
    if (text(0, 8) === "\x89PNG\r\n\x1a\n" && text(12, 16) === "IHDR") {
      width = view.getUint32(16); height = view.getUint32(20);
    } else if (text(0, 4) === "RIFF" && text(8, 12) === "WEBP") {
      if (text(12, 16) === "VP8X") {
        width = 1 + bytes[24] + (bytes[25] << 8) + (bytes[26] << 16);
        height = 1 + bytes[27] + (bytes[28] << 8) + (bytes[29] << 16);
      } else if (text(12, 16) === "VP8L" && bytes[20] === 0x2f) {
        width = 1 + bytes[21] + ((bytes[22] & 0x3f) << 8);
        height = 1 + (bytes[22] >> 6) + (bytes[23] << 2) + ((bytes[24] & 0x0f) << 10);
      } else if (text(12, 16) === "VP8 " && text(23, 26) === "\x9d\x01\x2a") {
        width = view.getUint16(26, true) & 0x3fff; height = view.getUint16(28, true) & 0x3fff;
      }
    } else if (bytes[0] === 0xff && bytes[1] === 0xd8) {
      for (let offset = 2; offset + 4 <= bytes.length;) {
        if (bytes[offset++] !== 0xff) return null;
        while (bytes[offset] === 0xff) offset += 1;
        const marker = bytes[offset++];
        if (marker === 0xda || marker === 0xd9) break;
        const length = view.getUint16(offset);
        if (length < 2 || offset + length > bytes.length) return null;
        if (marker === 0xe1 && text(offset + 2, offset + 8) === "Exif\0\0") {
          const tiff = offset + 8;
          const little = text(tiff, tiff + 2) === "II";
          if ((!little && text(tiff, tiff + 2) !== "MM") || view.getUint16(tiff + 2, little) !== 42) return null;
          const directory = tiff + view.getUint32(tiff + 4, little);
          const count = view.getUint16(directory, little);
          if (directory < tiff || directory + 2 + count * 12 > offset + length) return null;
          for (let index = 0; index < count; index += 1) {
            const tag = directory + 2 + index * 12;
            if (view.getUint16(tag, little) === 0x112) {
              if (view.getUint16(tag + 2, little) !== 3 || view.getUint32(tag + 4, little) !== 1) return null;
              orientation = view.getUint16(tag + 8, little);
            }
          }
        }
        if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb].includes(marker)) {
          if (length < 7) return null;
          height = view.getUint16(offset + 3); width = view.getUint16(offset + 5);
          break;
        }
        offset += length;
      }
    }
  } catch { return null; }
  if (!width || !height || width > 16384 || height > 16384 || width * height > 64_000_000 || orientation < 1 || orientation > 8) return null;
  return orientation >= 5 ? [height, width] : [width, height];
}

type PreviewPlatform = {
  decode: typeof createImageBitmap;
  encode: (bitmap: ImageBitmap) => Promise<Blob | null>;
  createUrl: (blob: Blob) => string;
  revokeUrl: (url: string) => void;
};

function browserPlatform(): PreviewPlatform | null {
  if (typeof globalThis.createImageBitmap !== "function") return null;
  return {
    decode: globalThis.createImageBitmap.bind(globalThis),
    encode: (bitmap) => new Promise((resolve) => {
      const canvas = document.createElement("canvas");
      canvas.width = bitmap.width; canvas.height = bitmap.height;
      const context = canvas.getContext("2d");
      if (!context) { resolve(null); return; }
      context.fillStyle = "white"; context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(bitmap, 0, 0);
      canvas.toBlob((blob) => { canvas.width = 0; canvas.height = 0; resolve(blob); }, "image/jpeg", 0.75);
    }),
    createUrl: (blob) => URL.createObjectURL(blob),
    revokeUrl: (url) => URL.revokeObjectURL(url),
  };
}

/** One decoder across file selections/children. Only small derivative URLs reach an <img>. */
export function startLocalPhotoPreviews(files: File[], publish: (index: number, url: string) => void,
  platform: PreviewPlatform | null = browserPlatform()): () => void {
  let cancelled = false;
  const urls = new Set<string>();
  if (platform) files.forEach((file, index) => {
    previewQueue = previewQueue.then(async () => {
      if (cancelled) return;
      const dimensions = photoPreviewDimensions(new Uint8Array(await file.slice(0, HEADER_BYTES).arrayBuffer()));
      if (!dimensions || cancelled) return;
      const scale = Math.min(1, EDGE / Math.max(...dimensions));
      const bitmap = await platform.decode(file, { imageOrientation: "from-image", resizeWidth: Math.max(1, Math.round(dimensions[0] * scale)), resizeHeight: Math.max(1, Math.round(dimensions[1] * scale)), resizeQuality: "high" });
      try {
        // An older WebView may ignore resize options: close it, never publish a full-size image.
        if (cancelled || bitmap.width > EDGE || bitmap.height > EDGE) return;
        const blob = await platform.encode(bitmap);
        if (!blob || blob.size > 128 * 1024 || cancelled) return;
        const url = platform.createUrl(blob);
        urls.add(url);
        publish(index, url);
      } finally { bitmap.close(); }
    }).catch(() => { /* A filename/selection placeholder remains available on unsupported inputs. */ });
  });
  return () => { cancelled = true; for (const url of urls) platform?.revokeUrl(url); urls.clear(); };
}
