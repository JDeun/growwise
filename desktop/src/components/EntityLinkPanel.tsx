import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getEntityBacklinks,
  listChildren,
  shareEntityWithChild,
  type ChildProfile,
  type EntityBacklinks,
} from "../api";
import "./EntityLinkPanel.css";

interface EntityLinkPanelProps {
  entityId: string;
  ownerChildId?: string | null;
  label?: string;
}

function messageFrom(error: unknown): string {
  if (error instanceof Error) return error.message;
  return typeof error === "string" ? error : "연결 정보를 처리하지 못했습니다.";
}

export function EntityLinkPanel({
  entityId,
  ownerChildId = null,
  label = "다른 아이와 연결",
}: EntityLinkPanelProps) {
  const [open, setOpen] = useState(false);
  const [children, setChildren] = useState<ChildProfile[]>([]);
  const [graph, setGraph] = useState<EntityBacklinks | null>(null);
  const [targetChildId, setTargetChildId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [nextChildren, nextGraph] = await Promise.all([
      listChildren(),
      getEntityBacklinks(entityId),
    ]);
    setChildren(nextChildren);
    setGraph(nextGraph);
  }, [entityId]);

  useEffect(() => {
    if (!open) return;
    void refresh().catch((loadError) => setError(messageFrom(loadError)));
  }, [open, refresh]);

  const linkedChildIds = useMemo(() => {
    const ids = new Set<string>();
    for (const item of graph?.outgoing ?? []) {
      if (item.link.relation === "child_scope") ids.add(item.link.target_id);
    }
    return ids;
  }, [graph]);

  const candidates = children.filter(
    (child) => child.id !== ownerChildId && !linkedChildIds.has(child.id),
  );

  const linkedChildren = children.filter((child) => linkedChildIds.has(child.id));

  async function handleShare() {
    if (!targetChildId || busy) return;
    setBusy(true);
    setError(null);
    try {
      await shareEntityWithChild(entityId, targetChildId);
      setTargetChildId("");
      await refresh();
    } catch (shareError) {
      setError(messageFrom(shareError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="entity-link-panel">
      <button
        className="quiet-button"
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        {linkedChildIds.size > 0 ? `연결 ${linkedChildIds.size}명` : label}
      </button>

      {open && (
        <div className="entity-link-popover">
          <strong>문서 연결</strong>
          <p className="muted">
            원본을 복제하지 않고 같은 문서를 다른 아이의 맥락에 연결합니다.
          </p>

          {linkedChildren.length > 0 && (
            <div className="entity-link-chip-list" aria-label="연결된 아이">
              {linkedChildren.map((child) => (
                <span key={child.id}>{child.nickname || child.id}</span>
              ))}
            </div>
          )}

          {candidates.length > 0 ? (
            <div className="entity-link-share-row">
              <select
                value={targetChildId}
                onChange={(event) => setTargetChildId(event.target.value)}
                disabled={busy}
                aria-label="연결할 아이"
              >
                <option value="">아이 선택</option>
                {candidates.map((child) => (
                  <option key={child.id} value={child.id}>
                    {child.nickname || child.id}
                  </option>
                ))}
              </select>
              <button
                className="quiet-button"
                type="button"
                disabled={!targetChildId || busy}
                onClick={() => void handleShare()}
              >
                {busy ? "연결 중…" : "연결"}
              </button>
            </div>
          ) : (
            <p className="muted">추가로 연결할 아이가 없습니다.</p>
          )}

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
