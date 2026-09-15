import { useState, type PropsWithChildren, type ReactNode } from "react";

import { WorkspaceNav, type WorkspaceView } from "./WorkspaceNav";

type WorkspaceShellProps = PropsWithChildren<{
  initialView?: WorkspaceView;
  renderWorkspace: (activeView: WorkspaceView) => ReactNode;
}>;

export function WorkspaceShell({
  initialView = "home",
  renderWorkspace,
}: WorkspaceShellProps) {
  const [activeView, setActiveView] = useState<WorkspaceView>(initialView);

  return (
    <>
      <WorkspaceNav activeView={activeView} onChange={setActiveView} />
      <div className="workspace-shell" data-active-workspace={activeView}>
        {renderWorkspace(activeView)}
      </div>
    </>
  );
}
