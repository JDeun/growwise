import "./WorkspacePlaceholder.css";

import { WORKSPACE_LABELS } from "./workspaceLabels";
import type { WorkspaceView } from "./workspaceTypes";

type WorkspacePlaceholderProps = { view: WorkspaceView };

export function WorkspacePlaceholder({ view }: WorkspacePlaceholderProps) {
  return (
    <section className="workspace workspace-placeholder" data-workspace-view={view}>
      <p className="eyebrow">WORKSPACE</p>
      <h2>{WORKSPACE_LABELS[view]}</h2>
      <p className="muted">기존 GrowWise 기능을 이 작업공간으로 안전하게 이동하는 중입니다.</p>
    </section>
  );
}
