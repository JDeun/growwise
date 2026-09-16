import type { WorkspaceLayoutKey } from "./workspaceLayout";
import type { WorkspaceView } from "./workspaceTypes";

export const WORKSPACE_MIGRATION: Record<WorkspaceLayoutKey, WorkspaceView> = {
  "child-context": "home",
  observations: "observations",
  photos: "photos",
  growth: "growth",
  activities: "activities",
  search: "search",
  library: "library",
  materials: "materials",
  settings: "settings",
};
