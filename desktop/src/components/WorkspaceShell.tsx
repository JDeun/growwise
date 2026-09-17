import { useState, type ReactNode } from "react";

import "./WorkspaceShell.css";
import { WorkspaceNav } from "./WorkspaceNav";
import { WORKSPACE_LABELS } from "./workspaceLabels";
import { readWorkspaceView, writeWorkspaceView } from "./workspaceStorage";
import type { WorkspaceView } from "./workspaceTypes";

type WorkspaceShellProps = {
  initialView?: WorkspaceView;
  renderWorkspace: (
    activeView: WorkspaceView,
    navigate: (view: WorkspaceView) => void,
  ) => ReactNode;
};

export function WorkspaceShell({ initialView, renderWorkspace }: WorkspaceShellProps) {
  const [activeView, setActiveView] = useState<WorkspaceView>(() => {
    if (initialView) return initialView;
    if (typeof window === "undefined") return "home";
    return readWorkspaceView(window.localStorage);
  });

  function handleChange(view: WorkspaceView) {
    setActiveView(view);
    if (typeof window !== "undefined") writeWorkspaceView(window.localStorage, view);
  }

  return (
    <div className="workspace-shell-root">
      <a className="skip-link" href="#workspace-panel">
        작업공간 본문으로 바로가기
      </a>
      <WorkspaceNav activeView={activeView} onChange={handleChange} />
      <div
        id="workspace-panel"
        className="workspace-shell"
        role="region"
        aria-label={`${WORKSPACE_LABELS[activeView]} 작업공간`}
        tabIndex={-1}
        data-active-workspace={activeView}
      >
        {renderWorkspace(activeView, handleChange)}
      </div>
    </div>
  );
}
