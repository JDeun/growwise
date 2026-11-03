import { describe, expect, it, vi } from "vitest";

import type { PhotoThumbnailContent } from "./api";
import { createPhotoThumbnailLoader, THUMBNAIL_CACHE_SIZE } from "./photo-thumbnails";

function thumbnail(childId: string, assetId: string): PhotoThumbnailContent {
  return {
    asset: { id:assetId,child_id:childId,original_filename:"photo.jpg",mime_type:"image/jpeg",
      relative_path:`photos/${childId}/photo.jpg`,sha256:"synthetic",byte_size:2000,width:1600,height:1000,
      captured_at:null,metadata_summary:{},caption:null,caption_model:null },
    mime_type:"image/jpeg",width:384,height:240,data_base64:"/9j/synthetic",
  };
}

describe("bounded lazy thumbnail loading", () => {
  it("deduplicates visible requests and never fetches more than two at once", async () => {
    const releases: Array<() => void> = [];
    let active = 0;
    let peak = 0;
    const fetch = vi.fn((child: string, asset: string) => new Promise<PhotoThumbnailContent>((resolve) => {
      active += 1; peak = Math.max(peak, active);
      releases.push(() => { active -= 1; resolve(thumbnail(child,asset)); });
    }));
    const loader = createPhotoThumbnailLoader(fetch);
    const first = loader.load("child-a","one");
    const duplicate = loader.load("child-a","one");
    const second = loader.load("child-a","two");
    const third = loader.load("child-a","three");
    expect(fetch).toHaveBeenCalledTimes(2);
    releases.shift()!();
    await first;
    await duplicate;
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
    releases.shift()!(); releases.shift()!();
    await Promise.all([second,third]);
    expect(peak).toBe(2);
    loader.clear();
  });

  it("drops queued offscreen requests and ignores an old child's late result after scope clear", async () => {
    const releases: Array<() => void> = [];
    const fetch = vi.fn((child: string, asset: string) => new Promise<PhotoThumbnailContent>((resolve) => {
      releases.push(() => resolve(thumbnail(child,asset)));
    }));
    const loader = createPhotoThumbnailLoader(fetch);
    const receive = vi.fn();
    const failed = vi.fn();
    loader.request("child-a","one",receive,failed);
    loader.request("child-a","two",receive,failed);
    const cancel = loader.request("child-a","offscreen",receive,failed);
    cancel(); // Both decoder slots are occupied: this request must never start.
    loader.clear();
    expect(failed).toHaveBeenCalledTimes(2);
    const current = loader.load("child-b","one");
    expect(fetch).toHaveBeenCalledTimes(2); // Previous scope still counts toward the concurrency limit.
    releases.shift()!();
    releases.shift()!();
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
    releases.shift()!();
    await current;
    expect(receive).not.toHaveBeenCalled();
    expect(fetch.mock.calls).toEqual([["child-a","one"],["child-a","two"],["child-b","one"]]);
    loader.clear();
  });

  it("evicts old cached previews and refetches them while keeping recent entries", async () => {
    const fetch = vi.fn(async (child: string, asset: string) => thumbnail(child,asset));
    const loader = createPhotoThumbnailLoader(fetch);
    for (let index=0;index<=THUMBNAIL_CACHE_SIZE;index+=1) await loader.load("child-a",String(index));
    const count = fetch.mock.calls.length;
    await loader.load("child-a",String(THUMBNAIL_CACHE_SIZE));
    expect(fetch).toHaveBeenCalledTimes(count);
    await loader.load("child-a","0");
    expect(fetch).toHaveBeenCalledTimes(count+1);
    await loader.load("child-b","0");
    expect(fetch).toHaveBeenCalledWith("child-b","0");
    loader.clear();
  });

  it("rejects oversized or mismatched previews instead of caching private or full-size payloads", async () => {
    const loader = createPhotoThumbnailLoader(async () => thumbnail("another-child","asset"));
    await expect(loader.load("child-a","asset")).rejects.toThrow("올바르지");
    const large = createPhotoThumbnailLoader(async () => ({...thumbnail("child-a","asset"),width:1600}));
    await expect(large.load("child-a","asset")).rejects.toThrow("올바르지");
    loader.clear(); large.clear();
  });
});
