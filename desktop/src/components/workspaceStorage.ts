import { isWorkspaceView } from "./workspaceViews";
import type { WorkspaceView } from "./workspaceTypes";

export const LAST_WORKSPACE_KEY = "growwise:last-workspace-view";

export function readWorkspaceView(storage: Pick<Storage, "getItem">): WorkspaceView {
  try {
    const stored = storage.getItem(LAST_WORKSPACE_KEY);
    return stored && isWorkspaceView(stored) ? stored : "home";
  } catch {
    return "home";
  }
}

export function writeWorkspaceView(storage: Pick<Storage, "setItem">, view: WorkspaceView): void {
  try {
    storage.setItem(LAST_WORKSPACE_KEY, view);
  } catch {
    // Storage may be unavailable in hardened/private environments; navigation still works in memory.
  }
}
