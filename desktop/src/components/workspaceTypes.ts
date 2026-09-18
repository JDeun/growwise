export type WorkspaceView =
  | "home"
  | "profile"
  | "photos"
  | "learning"
  | "materials"
  | "conversation"
  | "backup"
  | "settings"
  | "help"
  // Legacy internal routes remain temporarily routable while their features are
  // recomposed into the product workspaces above. They are never rendered in
  // the primary sidebar and persisted legacy values are migrated on read.
  | "observations"
  | "growth"
  | "activities"
  | "search"
  | "discovery"
  | "library";
