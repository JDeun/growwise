import { useState, type ReactNode } from "react";

import "./WorkspaceShell.css";
import { WorkspaceNav } from "./WorkspaceNav";
import { readWorkspaceView, writeWorkspaceView } from "./workspaceStorage";
import type { WorkspaceView } from "./workspaceTypes";

type WorkspaceShellProps = {
  initialView?: WorkspaceView;
  renderWorkspace: (activeView: WorkspaceView) => ReactNode;
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
      <WorkspaceNav activeView={activeView} onChange={handleChange} />
      <main className="workspace-shell" data-active-workspace={activeView}>
        {renderWorkspace(activeView)}
      </main>
    </div>
  );
}
