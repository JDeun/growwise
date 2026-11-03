import { useEffect, useRef, useState } from "react";

import type { PhotoThumbnailLoader } from "../photo-thumbnails";
import "./PhotoThumbnail.css";

export function PhotoThumbnail({ childId, assetId, loader, alt = "" }: {
  childId: string; assetId: string; loader: PhotoThumbnailLoader; alt?: string;
}) {
  const element = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const node = element.current;
    if (!node) return;
    if (typeof globalThis.IntersectionObserver !== "function") {
      let frame = 0;
      const check = () => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          const box = node.getBoundingClientRect();
          setVisible(box.bottom >= -160 && box.top <= window.innerHeight + 160);
        });
      };
      window.addEventListener("scroll", check, true);
      window.addEventListener("resize", check);
      check();
      return () => {
        cancelAnimationFrame(frame);
        window.removeEventListener("scroll", check, true);
        window.removeEventListener("resize", check);
      };
    }
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { rootMargin: "160px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    setUrl(null);
    setError(false);
    if (!visible) return;
    return loader.request(childId, assetId, (preview) => setUrl(preview.url), () => setError(true));
  }, [loader, childId, assetId, visible, attempt]);

  return (
    <div className="photo-thumbnail" ref={element}>
      {url ? <img src={url} alt={alt} loading="lazy" decoding="async" onError={() => { loader.invalidate(childId, assetId); setUrl(null); setError(true); }} />
        : error ? <button className="quiet-button" type="button" onClick={() => setAttempt((value) => value + 1)}>미리보기 다시 불러오기</button>
          : <span aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="10" r="2" /><path d="m21 15-4.5-4.5L8 19" /></svg></span>}
    </div>
  );
}
