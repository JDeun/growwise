import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ActiveChildProvider } from "./active-child-context";
import { WorkspaceShell } from "./components";
import {
  DiscoveryWorkspace,
  HomeDashboard,
  HelpWorkspace,
  LearningRecordWorkspace,
  LearningWorkspaceHub,
  MaterialsWorkspaceHub,
  PhotoActivityWorkspace,
  ProfileWorkspaceHub,
} from "./features";
import { applyDocumentLocale, detectBrowserLocale } from "./i18n";
import "./styles.css";
import "./tokens.css";
import "./brand.css";
import "./activity-provenance.css";
import "./print.css";
import "./accessibility.css";

applyDocumentLocale(detectBrowserLocale());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ActiveChildProvider>
      <WorkspaceShell
        renderWorkspace={(activeView, navigate) => (
          <>
            {activeView === "learning" ? (
              <LearningWorkspaceHub
                renderRecords={(active) => <LearningRecordWorkspace active={active} embedded />}
                observationApp={<App activeView={activeView} />}
              />
            ) : activeView === "profile" ? (
              <ProfileWorkspaceHub
                app={<App activeView={activeView} />}
                renderLearning={(active) => <LearningRecordWorkspace active={active} embedded />}
                onNavigate={navigate}
              />
            ) : activeView === "materials" ? (
              <MaterialsWorkspaceHub
                app={<App activeView={activeView} />}
                renderDiscovery={(active) => <DiscoveryWorkspace active={active} />}
              />
            ) : (
              activeView !== "home"
              && activeView !== "photos"
              && activeView !== "discovery"
              && activeView !== "help"
              && <App activeView={activeView} />
            )}
            <HomeDashboard active={activeView === "home"} onNavigate={navigate} />
            <PhotoActivityWorkspace active={activeView === "photos"} />
            <HelpWorkspace active={activeView === "help"} />
            <DiscoveryWorkspace active={activeView === "discovery"} />
          </>
        )}
      />
    </ActiveChildProvider>
  </StrictMode>,
);
