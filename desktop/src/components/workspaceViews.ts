import type { WorkspaceView } from "./WorkspaceNav";

export const WORKSPACE_VIEWS: readonly WorkspaceView[] = [
  "home",
  "observations",
  "growth",
  "activities",
  "search",
  "library",
  "materials",
  "settings",
] as const;

export function isWorkspaceView(value: string): value is WorkspaceView {
  return WORKSPACE_VIEWS.includes(value as WorkspaceView);
}
