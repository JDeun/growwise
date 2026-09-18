import { useState, type ReactNode } from "react";

import "./WorkspaceShell.css";
import { WorkspaceNav } from "./WorkspaceNav";
import { WORKSPACE_DESCRIPTIONS } from "./workspaceDescriptions";
import { WORKSPACE_LABELS } from "./workspaceLabels";
import { readWorkspaceView, writeWorkspaceView } from "./workspaceStorage";
import type { WorkspaceView } from "./workspaceTypes";

type WorkspaceShellProps = {
  initialView?: WorkspaceView;
  renderWorkspace: (
    activeView: WorkspaceView,
    navigate: (view: WorkspaceView) => void,
  ) => ReactNode;
};

export function WorkspaceShell({ initialView, renderWorkspace }: WorkspaceShellProps) {
  const [activeView, setActiveView] = useState<WorkspaceView>(() => {
    if (initialView) return initialView;
    if (typeof window === "undefined") return "home";
    return readWorkspaceView(window.localStorage);
  });

  function handleChange(view: WorkspaceView) {
    setActiveView(view);
    if (typeof window !== "undefined") writeWorkspaceView(window.localStorage, view);
  }

  return (
    <div className="workspace-shell-root">
      <a className="skip-link" href="#workspace-panel">
        작업공간 본문으로 바로가기
      </a>
      <WorkspaceNav activeView={activeView} onChange={handleChange} />
      <div className="workspace-shell-main">
        <header className="workspace-shell-topbar">
          <div className="workspace-shell-heading">
            <span>GrowWise</span>
            <h1>{WORKSPACE_LABELS[activeView]}</h1>
            <p>{WORKSPACE_DESCRIPTIONS[activeView]}</p>
          </div>
          <div className="workspace-shell-actions">
            <button
              type="button"
              className="workspace-global-search"
              onClick={() => handleChange("search")}
              aria-label="기록과 자료 검색으로 이동"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="11" cy="11" r="6.5" />
                <path d="m16 16 4 4" />
              </svg>
              <span>기록과 자료 검색</span>
              <kbd>⌘ K</kbd>
            </button>
            <span className="workspace-local-badge">
              <i aria-hidden="true" />
              Local first
            </span>
          </div>
        </header>
        <div
          id="workspace-panel"
          className="workspace-shell"
          role="region"
          aria-label={`${WORKSPACE_LABELS[activeView]} 작업공간`}
          tabIndex={-1}
          data-active-workspace={activeView}
        >
          {renderWorkspace(activeView, handleChange)}
        </div>
      </div>
    </div>
  );
}
