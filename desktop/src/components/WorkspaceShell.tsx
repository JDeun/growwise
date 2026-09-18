import { useState, type ReactNode } from "react";

import { useActiveChild } from "../active-child-context";
import { ChildAvatar } from "./ChildAvatar";
import "./WorkspaceShell.css";
import { WorkspaceNav } from "./WorkspaceNav";
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
  const { activeChild } = useActiveChild();
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
      <main className="workspace-main">
        <header className="workspace-topbar">
          <div className="workspace-topbar-title">
            <small>GrowWise</small>
            <h1>{WORKSPACE_LABELS[activeView]}</h1>
          </div>
          <div className="workspace-topbar-actions">
            <button
              type="button"
              className="workspace-search-trigger"
              onClick={() => handleChange("search")}
              aria-label="기록과 자료 검색으로 이동"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></svg>
              <span>기록과 자료 검색</span>
              <kbd>⌘ K</kbd>
            </button>
            <button
              type="button"
              className="workspace-quick-record"
              onClick={() => handleChange("observations")}
            >
              <span aria-hidden="true">＋</span>
              새 기록
            </button>
            <button
              type="button"
              className="workspace-topbar-avatar"
              onClick={() => handleChange("profile")}
              aria-label="아이 프로필로 이동"
            >
              <ChildAvatar child={activeChild} size="sm" />
            </button>
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
      </main>
    </div>
  );
}
