import "./WorkspacePlaceholder.css";

import { WORKSPACE_DESCRIPTIONS } from "./workspaceDescriptions";
import { WORKSPACE_LABELS } from "./workspaceLabels";
import type { WorkspaceView } from "./workspaceTypes";

type WorkspacePlaceholderProps = { view: WorkspaceView };

export function WorkspacePlaceholder({ view }: WorkspacePlaceholderProps) {
  return (
    <section className="workspace workspace-placeholder" data-workspace-view={view}>
      <p className="eyebrow">WORKSPACE</p>
      <h2>{WORKSPACE_LABELS[view]}</h2>
      <p className="muted">{WORKSPACE_DESCRIPTIONS[view]}</p>
    </section>
  );
}
