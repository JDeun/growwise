import { getPhotoThumbnail, type PhotoAsset, type PhotoThumbnailContent } from "./api";

export const THUMBNAIL_CACHE_SIZE = 32;
export const THUMBNAIL_CONCURRENCY = 2;
export interface PhotoPreview { asset: PhotoAsset; url: string; width: number; height: number }
type Listener = { resolve: (preview: PhotoPreview) => void; reject: (error: unknown) => void };
type Request = { childId: string; assetId: string; generation: number; started: boolean; listeners: Set<Listener> };

export function createPhotoThumbnailLoader(fetchThumbnail = getPhotoThumbnail) {
  const cache = new Map<string, PhotoPreview>();
  const requests = new Map<string, Request>();
  let generation = 0;
  let active = 0;
  const keyFor = (childId: string, assetId: string) => `${childId}/${assetId}`;

  function preview(content: PhotoThumbnailContent, job: Request): PhotoPreview {
    if (content.asset.id !== job.assetId || content.asset.child_id !== job.childId
      || content.mime_type !== "image/jpeg" || content.width < 1 || content.height < 1
      || content.width > 384 || content.height > 384 || content.data_base64.length > 174764) {
      throw new Error("사진 미리보기 응답이 올바르지 않습니다.");
    }
    return { asset: content.asset, url: `data:image/jpeg;base64,${content.data_base64}`, width: content.width, height: content.height };
  }

  function pump() {
    for (const [key, job] of requests) {
      if (active >= THUMBNAIL_CONCURRENCY) break;
      if (job.started || job.listeners.size === 0) continue;
      active += 1;
      job.started = true;
      void fetchThumbnail(job.childId, job.assetId).then((content) => {
        if (job.generation !== generation) return;
        const result = preview(content, job);
        cache.delete(key);
        cache.set(key, result);
        while (cache.size > THUMBNAIL_CACHE_SIZE) cache.delete(cache.keys().next().value!);
        for (const listener of job.listeners) listener.resolve(result);
      }).catch((error: unknown) => {
        for (const listener of job.listeners) listener.reject(error);
      }).finally(() => {
        active -= 1;
        if (requests.get(key) === job) requests.delete(key);
        pump();
      });
    }
  }

  function request(childId: string, assetId: string, resolve: Listener["resolve"], reject: Listener["reject"]) {
    const key = keyFor(childId, assetId);
    const hit = cache.get(key);
    if (hit) {
      cache.delete(key); cache.set(key, hit);
      resolve(hit);
      return () => undefined;
    }
    let job = requests.get(key);
    if (!job) {
      job = { childId, assetId, generation, started: false, listeners: new Set() };
      requests.set(key, job);
    }
    const listener = { resolve, reject };
    job.listeners.add(listener);
    pump();
    return () => {
      job.listeners.delete(listener);
      if (!job.started && job.listeners.size === 0) requests.delete(key);
    };
  }

  return {
    request,
    invalidate(childId: string, assetId: string) { cache.delete(keyFor(childId, assetId)); },
    load: (childId: string, assetId: string) => new Promise<PhotoPreview>((resolve, reject) => request(childId, assetId, resolve, reject)),
    clear() {
      generation += 1;
      cache.clear();
      for (const job of requests.values()) {
        for (const listener of job.listeners) listener.reject(new Error("사진 미리보기 작업을 취소했습니다."));
        job.listeners.clear();
      }
      requests.clear();
    },
  };
}

export type PhotoThumbnailLoader = ReturnType<typeof createPhotoThumbnailLoader>;
