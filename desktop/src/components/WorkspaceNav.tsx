import "./WorkspaceNav.css";

import { WORKSPACE_LABELS } from "./workspaceLabels";
import { WORKSPACE_VIEWS } from "./workspaceViews";

export type WorkspaceView =
  | "home"
  | "observations"
  | "growth"
  | "activities"
  | "search"
  | "library"
  | "materials"
  | "settings";

type WorkspaceNavProps = {
  activeView: WorkspaceView;
  onChange: (view: WorkspaceView) => void;
};

export function WorkspaceNav({ activeView, onChange }: WorkspaceNavProps) {
  return (
    <nav className="workspace-nav" aria-label="GrowWise workspace">
      {WORKSPACE_VIEWS.map((view) => {
        const active = activeView === view;
        return (
          <button
            key={view}
            type="button"
            className={`workspace-nav__item ${active ? "active" : ""}`}
            aria-current={active ? "page" : undefined}
            onClick={() => onChange(view)}
          >
            {WORKSPACE_LABELS[view]}
          </button>
        );
      })}
    </nav>
  );
}
