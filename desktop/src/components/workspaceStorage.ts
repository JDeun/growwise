import { isProductWorkspaceView } from "./workspaceViews";
import type { WorkspaceView } from "./workspaceTypes";

export const LAST_WORKSPACE_KEY = "growwise:last-workspace-view:v2";
export const LEGACY_LAST_WORKSPACE_KEY = "growwise:last-workspace-view";

const LEGACY_WORKSPACE_MIGRATION: Readonly<Record<string, WorkspaceView>> = {
  home: "home",
  profile: "profile",
  observations: "learning",
  photos: "photos",
  learning: "learning",
  growth: "profile",
  activities: "materials",
  search: "conversation",
  discovery: "materials",
  library: "materials",
  materials: "materials",
  settings: "backup",
};

export function readWorkspaceView(storage: Pick<Storage, "getItem">): WorkspaceView {
  try {
    const stored = storage.getItem(LAST_WORKSPACE_KEY);
    if (stored && isProductWorkspaceView(stored)) return stored;

    const legacy = storage.getItem(LEGACY_LAST_WORKSPACE_KEY);
    return legacy ? LEGACY_WORKSPACE_MIGRATION[legacy] ?? "home" : "home";
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
