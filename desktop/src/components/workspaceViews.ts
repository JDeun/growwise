import type { WorkspaceView } from "./workspaceTypes";

export const PRODUCT_WORKSPACE_VIEWS: readonly WorkspaceView[] = [
  "home",
  "profile",
  "learning",
  "materials",
  "photos",
  "conversation",
  "backup",
  "settings",
  "help",
] as const;

export const LEGACY_WORKSPACE_VIEWS: readonly WorkspaceView[] = [
  "observations",
  "growth",
  "activities",
  "search",
  "discovery",
  "library",
] as const;

export const WORKSPACE_VIEWS: readonly WorkspaceView[] = [
  ...PRODUCT_WORKSPACE_VIEWS,
  ...LEGACY_WORKSPACE_VIEWS,
] as const;

export function isWorkspaceView(value: string): value is WorkspaceView {
  return WORKSPACE_VIEWS.includes(value as WorkspaceView);
}
