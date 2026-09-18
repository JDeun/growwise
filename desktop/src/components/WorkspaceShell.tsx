import { useEffect, useState, type ReactNode } from "react";

import { useOptionalActiveChild } from "../active-child-context";
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
  const activeChild = useOptionalActiveChild()?.activeChild ?? null;
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [activeView, setActiveView] = useState<WorkspaceView>(() => {
    if (initialView) return initialView;
    if (typeof window === "undefined") return "home";
    return readWorkspaceView(window.localStorage);
  });

  function handleChange(view: WorkspaceView) {
    setNotificationsOpen(false);
    setActiveView(view);
    if (typeof window !== "undefined") writeWorkspaceView(window.localStorage, view);
  }

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "k") return;
      event.preventDefault();
      setActiveView("conversation");
      writeWorkspaceView(window.localStorage, "conversation");
      window.requestAnimationFrame(() => {
        document.querySelector<HTMLElement>(
          ".conversation-workspace-grid textarea, .conversation-section textarea, .search-section .search-form input",
        )?.focus();
      });
    }

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  return (
    <div className="workspace-shell-root">
      <a className="skip-link" href="#workspace-panel">
        작업공간 본문으로 바로가기
      </a>
      <WorkspaceNav activeView={activeView} onChange={handleChange} />
      <main className="workspace-main">
        <header className="workspace-topbar">
          <div className="workspace-topbar-actions">
            <button
              type="button"
              className="workspace-search-trigger"
              onClick={() => handleChange("conversation")}
              aria-label="대화와 기록 검색으로 이동"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></svg>
              <span>검색어를 입력하세요...</span>
            </button>

            <div className="workspace-notifications">
              <button
                type="button"
                className="workspace-icon-button"
                aria-label="알림"
                aria-expanded={notificationsOpen}
                aria-controls="workspace-notification-popover"
                onClick={() => setNotificationsOpen((current) => !current)}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6.5 9.5a5.5 5.5 0 0 1 11 0c0 6 2.2 6.5 2.2 6.5H4.3s2.2-.5 2.2-6.5Z"/>
                  <path d="M10 19h4"/>
                </svg>
              </button>
              {notificationsOpen && (
                <div id="workspace-notification-popover" className="workspace-notification-popover" role="status">
                  <strong>알림</strong>
                  <p>새로운 알림이 없습니다.</p>
                </div>
              )}
            </div>

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
