import type { WorkspaceLayoutKey } from "./workspaceLayout";
import type { WorkspaceView } from "./workspaceTypes";

export const WORKSPACE_MIGRATION: Record<WorkspaceLayoutKey, WorkspaceView> = {
  "child-context": "home",
  profile: "profile",
  observations: "learning",
  photos: "photos",
  "learning-records": "learning",
  growth: "profile",
  activities: "materials",
  search: "conversation",
  discovery: "materials",
  library: "materials",
  materials: "materials",
  backup: "backup",
  settings: "settings",
  help: "help",
};
