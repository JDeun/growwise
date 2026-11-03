import { describe, expect, it, vi } from "vitest";
import { photoPreviewDimensions, startLocalPhotoPreviews } from "./local-photo-previews";

function png(width: number, height: number): File {
  const bytes = new Uint8Array(24);
  bytes.set([137,80,78,71,13,10,26,10]);
  bytes.set([73,72,68,82],12);
  const view = new DataView(bytes.buffer);
  view.setUint32(16,width); view.setUint32(20,height);
  return new File([bytes], "synthetic.png", {type:"image/png"});
}

describe("small local photo previews", () => {
  it("reads dimensions without decoding and rejects oversized/malformed containers", async () => {
    expect(photoPreviewDimensions(new Uint8Array(await png(4032,3024).arrayBuffer()))).toEqual([4032,3024]);
    expect(photoPreviewDimensions(new Uint8Array(await png(100000,100000).arrayBuffer()))).toBeNull();
    expect(photoPreviewDimensions(new Uint8Array([137,80,78]))).toBeNull();
    const webp = new Uint8Array(30);
    webp.set([..."RIFF"].map(char=>char.charCodeAt(0))); webp.set([..."WEBPVP8X"].map(char=>char.charCodeAt(0)),8);
    webp[24]=127; webp[27]=63;
    expect(photoPreviewDimensions(webp)).toEqual([128,64]);
  });

  it("accounts for EXIF orientation before requesting an aspect-preserving resize", () => {
    const bytes = new Uint8Array(51);
    bytes.set([255,216,255,225,0,34,69,120,105,102,0,0,73,73,42,0,8,0,0,0,1,0,18,1,3,0,1,0,0,0,6,0,0,0,0,0,0,0,255,192,0,11,8,3,232,6,64,0,0]);
    expect(photoPreviewDimensions(bytes)).toEqual([1000,1600]);
  });

  it("serializes selections, closes bitmaps and revokes only derivative URLs on cancellation", async () => {
    const releases: Array<() => void> = [];
    const closed = vi.fn();
    const decode = vi.fn((_file: unknown, options?: ImageBitmapOptions) => new Promise<ImageBitmap>(resolve => {
      releases.push(() => resolve({width:options!.resizeWidth!,height:options!.resizeHeight!,close:closed} as ImageBitmap));
    }));
    const platform = {decode:decode as typeof createImageBitmap,encode:vi.fn(async()=>new Blob(["small JPEG"],{type:"image/jpeg"})),createUrl:vi.fn((blob: Blob)=> { expect(blob.size).toBeLessThan(128*1024); return "blob:derivative"; }),revokeUrl:vi.fn()};
    const oldPublish = vi.fn();
    const stopOld = startLocalPhotoPreviews([png(4032,3024),png(4000,3000)],oldPublish,platform);
    await vi.waitFor(()=>expect(decode).toHaveBeenCalledTimes(1));
    expect(decode.mock.calls[0][1]).toMatchObject({resizeWidth:384,resizeHeight:288,imageOrientation:"from-image"});
    stopOld();
    const nextPublish=vi.fn();
    const stopNext=startLocalPhotoPreviews([png(2000,1000)],nextPublish,platform);
    expect(decode).toHaveBeenCalledTimes(1);
    releases.shift()!();
    await vi.waitFor(()=>expect(decode).toHaveBeenCalledTimes(2));
    expect(oldPublish).not.toHaveBeenCalled();
    expect(platform.encode).not.toHaveBeenCalled();
    releases.shift()!();
    await vi.waitFor(()=>expect(nextPublish).toHaveBeenCalledWith(0,"blob:derivative"));
    expect(closed).toHaveBeenCalledTimes(2);
    expect(platform.createUrl.mock.calls[0][0].size).toBeLessThan(128*1024);
    stopNext();
    expect(platform.revokeUrl).toHaveBeenCalledExactlyOnceWith("blob:derivative");
  });

  it("keeps a placeholder when resizing is unsupported or a WebView ignores resize options", async () => {
    const publish = vi.fn();
    const stopMissing=startLocalPhotoPreviews([png(100,100)],publish,null);
    stopMissing();
    const closed=vi.fn();
    const platform={decode:vi.fn(async()=>({width:4000,height:3000,close:closed})) as unknown as typeof createImageBitmap,
      encode:vi.fn(async()=>new Blob()),createUrl:vi.fn(),revokeUrl:vi.fn()};
    const stop=startLocalPhotoPreviews([png(4000,3000)],publish,platform);
    await vi.waitFor(()=>expect(closed).toHaveBeenCalledTimes(1));
    expect(platform.encode).not.toHaveBeenCalled();
    expect(platform.createUrl).not.toHaveBeenCalled();
    expect(publish).not.toHaveBeenCalled();
    stop();
  });
});
