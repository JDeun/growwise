import type { WorkspaceView } from "./workspaceTypes";

export type WorkspaceLayoutKey =
  | "child-context"
  | "observations"
  | "photos"
  | "growth"
  | "activities"
  | "search"
  | "library"
  | "materials"
  | "settings";

export const WORKSPACE_LAYOUT: Record<WorkspaceView, readonly WorkspaceLayoutKey[]> = {
  home: ["child-context"],
  observations: ["observations"],
  photos: ["photos"],
  growth: ["growth"],
  activities: ["activities"],
  search: ["search"],
  library: ["library"],
  materials: ["materials"],
  settings: ["settings"],
};
