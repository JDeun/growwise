import type { PropsWithChildren } from "react";

import { WORKSPACE_DESCRIPTIONS } from "./workspaceDescriptions";
import { WORKSPACE_LABELS } from "./workspaceLabels";
import type { WorkspaceView } from "./workspaceTypes";

type WorkspaceFrameProps = PropsWithChildren<{ view: WorkspaceView }>;

export function WorkspaceFrame({ view, children }: WorkspaceFrameProps) {
  return (
    <section className="workspace-frame" data-workspace-view={view} aria-labelledby={`workspace-${view}-title`}>
      <header className="workspace-frame__header">
        <p className="eyebrow">WORKSPACE</p>
        <h2 id={`workspace-${view}-title`}>{WORKSPACE_LABELS[view]}</h2>
        <p className="muted">{WORKSPACE_DESCRIPTIONS[view]}</p>
      </header>
      {children}
    </section>
  );
}
