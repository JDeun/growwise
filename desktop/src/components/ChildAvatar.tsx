import { useEffect, useMemo, useState } from "react";

import { getPhotoAsset, type ChildProfile } from "../api";
import "./ChildAvatar.css";

type ChildAvatarSize = "sm" | "md" | "lg";

interface ChildAvatarProps {
  child: ChildProfile | null;
  size?: ChildAvatarSize;
  className?: string;
}

function initials(child: ChildProfile | null): string {
  const label = child?.nickname?.trim() || "?";
  return label.slice(0, 2).toUpperCase();
}

export function ChildAvatar({ child, size = "md", className = "" }: ChildAvatarProps) {
  const [source, setSource] = useState<string | null>(null);
  const avatarAssetId = child?.avatar_asset_id ?? null;

  useEffect(() => {
    let cancelled = false;
    setSource(null);
    if (!child || !avatarAssetId) return () => { cancelled = true; };

    void getPhotoAsset(child.id, avatarAssetId)
      .then(({ asset, data_base64 }) => {
        if (cancelled) return;
        setSource(`data:${asset.mime_type};base64,${data_base64}`);
      })
      .catch(() => {
        if (!cancelled) setSource(null);
      });

    return () => {
      cancelled = true;
    };
  }, [avatarAssetId, child]);

  const fallback = useMemo(() => initials(child), [child]);

  return (
    <span
      className={`child-avatar child-avatar--${size} ${className}`.trim()}
      aria-label={child ? `${child.nickname} 프로필 사진` : "아이 프로필 사진"}
      data-has-image={source ? "true" : "false"}
    >
      {source ? <img src={source} alt="" draggable={false} /> : <span aria-hidden="true">{fallback}</span>}
    </span>
  );
}
