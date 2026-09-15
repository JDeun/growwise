import type { ReactNode } from "react";

import type { WorkspaceView as WorkspaceViewName } from "./WorkspaceNav";

export type WorkspaceViewSlots = Partial<Record<WorkspaceViewName, ReactNode>>;

type WorkspaceViewProps = {
  activeView: WorkspaceViewName;
  slots: WorkspaceViewSlots;
};

export function WorkspaceView({ activeView, slots }: WorkspaceViewProps) {
  return <>{slots[activeView] ?? null}</>;
}
