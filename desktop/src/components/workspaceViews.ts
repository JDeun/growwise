import type { WorkspaceView } from "./workspaceTypes";

export const WORKSPACE_VIEWS: readonly WorkspaceView[] = [
  "home",
  "profile",
  "observations",
  "photos",
  "learning",
  "growth",
  "activities",
  "search",
  "discovery",
  "library",
  "materials",
  "settings",
] as const;

export function isWorkspaceView(value: string): value is WorkspaceView {
  return WORKSPACE_VIEWS.includes(value as WorkspaceView);
}
