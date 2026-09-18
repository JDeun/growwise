import type { WorkspaceView } from "./workspaceTypes";

export type WorkspaceLayoutKey =
  | "child-context"
  | "profile"
  | "observations"
  | "photos"
  | "learning-records"
  | "growth"
  | "activities"
  | "search"
  | "discovery"
  | "library"
  | "materials"
  | "backup"
  | "settings"
  | "help";

export const WORKSPACE_LAYOUT: Record<WorkspaceView, readonly WorkspaceLayoutKey[]> = {
  home: ["child-context"],
  profile: ["profile", "growth"],
  learning: ["learning-records", "observations"],
  materials: ["materials", "library", "discovery", "activities"],
  photos: ["photos"],
  conversation: ["search"],
  backup: ["backup"],
  settings: ["settings"],
  help: ["help"],
  observations: ["observations"],
  growth: ["growth"],
  activities: ["activities"],
  search: ["search"],
  discovery: ["discovery"],
  library: ["library"],
};
