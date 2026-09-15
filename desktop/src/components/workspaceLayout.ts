import type { WorkspaceView } from "./workspaceTypes";

export type WorkspaceLayoutKey =
  | "child-context"
  | "observations"
  | "growth"
  | "activities"
  | "search"
  | "library"
  | "materials"
  | "settings";

export const WORKSPACE_LAYOUT: Record<WorkspaceView, readonly WorkspaceLayoutKey[]> = {
  home: ["child-context"],
  observations: ["observations"],
  growth: ["growth"],
  activities: ["activities"],
  search: ["search"],
  library: ["library"],
  materials: ["materials"],
  settings: ["settings"],
};
