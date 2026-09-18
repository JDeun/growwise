import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";

import {
  deleteChildAvatar,
  getPhotoAsset,
  uploadChildAvatar,
  type ChildProfile,
} from "../api";
import "./ChildAvatar.css";

type ChildAvatarProps = {
  child: ChildProfile;
  size?: "sm" | "md" | "lg" | "xl";
  editable?: boolean;
  onUpdated?: (child: ChildProfile) => void;
};

const MAX_AVATAR_BYTES = 5 * 1024 * 1024;

function initials(value: string): string {
  const normalized = value.trim();
  if (!normalized) return "GW";
  return Array.from(normalized).slice(0, 2).join("").toUpperCase();
}

function readFileBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("프로필 사진을 읽지 못했습니다."));
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      const comma = result.indexOf(",");
      if (comma < 0) return reject(new Error("프로필 사진 형식을 읽지 못했습니다."));
      resolve(result.slice(comma + 1));
    };
    reader.readAsDataURL(file);
  });
}

export function ChildAvatar({
  child,
  size = "md",
  editable = false,
  onUpdated,
}: ChildAvatarProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fallback = useMemo(() => initials(child.nickname), [child.nickname]);

  useEffect(() => {
    let cancelled = false;
    const assetId = child.avatar_asset_id;
    if (!assetId) {
      setSrc(null);
      return () => {
        cancelled = true;
      };
    }

    void getPhotoAsset(child.id, assetId)
      .then(({ asset, data_base64 }) => {
        if (!cancelled) setSrc(`data:${asset.mime_type};base64,${data_base64}`);
      })
      .catch(() => {
        if (!cancelled) setSrc(null);
      });
    return () => {
      cancelled = true;
    };
  }, [child.avatar_asset_id, child.id]);

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("JPG, PNG, WebP 이미지만 사용할 수 있습니다.");
      return;
    }
    if (file.size > MAX_AVATAR_BYTES) {
      setError("프로필 사진은 5MB 이하로 선택해 주세요.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const dataBase64 = await readFileBase64(file);
      const updated = await uploadChildAvatar(child.id, file.name, file.type, dataBase64);
      onUpdated?.(updated);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "프로필 사진 저장에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!child.avatar_asset_id) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await deleteChildAvatar(child.id);
      setSrc(null);
      onUpdated?.(updated);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "프로필 사진 삭제에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`child-avatar child-avatar--${size} ${editable ? "child-avatar--editable" : ""}`}>
      <div className="child-avatar__media" aria-label={`${child.nickname} 프로필 사진`}>
        {src ? <img src={src} alt="" /> : <span aria-hidden="true">{fallback}</span>}
      </div>
      {editable ? (
        <div className="child-avatar__actions">
          <input
            ref={inputRef}
            className="child-avatar__input"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(event) => void handleFile(event)}
            disabled={busy}
          />
          <button
            type="button"
            className="child-avatar__edit"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
          >
            {busy ? "처리 중" : child.avatar_asset_id ? "사진 변경" : "사진 추가"}
          </button>
          {child.avatar_asset_id ? (
            <button
              type="button"
              className="child-avatar__remove"
              onClick={() => void handleDelete()}
              disabled={busy}
            >
              삭제
            </button>
          ) : null}
        </div>
      ) : null}
      {error ? <p className="child-avatar__error" role="alert">{error}</p> : null}
    </div>
  );
}
