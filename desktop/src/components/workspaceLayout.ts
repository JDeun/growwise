import type { WorkspaceView } from "./workspaceTypes";

export type WorkspaceLayoutKey =
  | "child-context"
  | "observations"
  | "photos"
  | "learning-records"
  | "growth"
  | "activities"
  | "search"
  | "discovery"
  | "library"
  | "materials"
  | "settings";

export const WORKSPACE_LAYOUT: Record<WorkspaceView, readonly WorkspaceLayoutKey[]> = {
  home: ["child-context"],
  observations: ["observations"],
  photos: ["photos"],
  learning: ["learning-records"],
  growth: ["growth"],
  activities: ["activities"],
  search: ["search"],
  discovery: ["discovery"],
  library: ["library"],
  materials: ["materials"],
  settings: ["settings"],
};
