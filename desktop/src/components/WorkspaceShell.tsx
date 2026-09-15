import { useState, type ReactNode } from "react";

import { WorkspaceNav } from "./WorkspaceNav";
import { readWorkspaceView, writeWorkspaceView } from "./workspaceStorage";
import type { WorkspaceView } from "./workspaceTypes";

type WorkspaceShellProps = {
  initialView?: WorkspaceView;
  renderWorkspace: (activeView: WorkspaceView) => ReactNode;
};

export function WorkspaceShell({ initialView, renderWorkspace }: WorkspaceShellProps) {
  const [activeView, setActiveView] = useState<WorkspaceView>(() => initialView ?? readWorkspaceView(window.localStorage));

  function handleChange(view: WorkspaceView) {
    setActiveView(view);
    writeWorkspaceView(window.localStorage, view);
  }

  return <><WorkspaceNav activeView={activeView} onChange={handleChange} /><div className="workspace-shell" data-active-workspace={activeView}>{renderWorkspace(activeView)}</div></>;
}
