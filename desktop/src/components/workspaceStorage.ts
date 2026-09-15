import { isWorkspaceView } from "./workspaceViews";
import type { WorkspaceView } from "./workspaceTypes";

export const LAST_WORKSPACE_KEY = "growwise:last-workspace-view";

export function readWorkspaceView(storage: Pick<Storage, "getItem">): WorkspaceView {
  const stored = storage.getItem(LAST_WORKSPACE_KEY);
  return stored && isWorkspaceView(stored) ? stored : "home";
}

export function writeWorkspaceView(storage: Pick<Storage, "setItem">, view: WorkspaceView): void {
  storage.setItem(LAST_WORKSPACE_KEY, view);
}
