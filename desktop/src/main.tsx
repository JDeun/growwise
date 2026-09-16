import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import PrintApprovedMaterials from "./PrintApprovedMaterials";
import { CapabilityStatus } from "./components/CapabilityStatus";
import { WorkspaceShell } from "./components";
import { HomeDashboard, PhotoActivityWorkspace } from "./features";
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
    <WorkspaceShell
      renderWorkspace={(activeView, navigate) => (
        <>
          <CapabilityStatus />
          {activeView !== "photos" && <App />}
          <HomeDashboard active={activeView === "home"} onNavigate={navigate} />
          <PhotoActivityWorkspace active={activeView === "photos"} />
        </>
      )}
    />
    <PrintApprovedMaterials />
  </StrictMode>,
);
