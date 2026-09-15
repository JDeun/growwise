import type { ReactNode } from "react";

import "./ViewStateNotice.css";

export type ViewStateNoticeKind = "loading" | "error" | "empty";

interface ViewStateNoticeProps {
  kind: ViewStateNoticeKind;
  title: string;
  description: string;
  action?: ReactNode;
}

export function ViewStateNotice({ kind, title, description, action }: ViewStateNoticeProps) {
  const liveProps =
    kind === "error"
      ? { role: "alert" as const }
      : { role: "status" as const, "aria-live": "polite" as const };

  return (
    <div className={`view-state-notice view-state-${kind}`} {...liveProps}>
      <span className="view-state-mark" aria-hidden="true">
        {kind === "loading" ? "…" : kind === "error" ? "!" : "·"}
      </span>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
        {action ? <div className="view-state-action">{action}</div> : null}
      </div>
    </div>
  );
}
