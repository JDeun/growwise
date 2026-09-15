import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import PrintApprovedMaterials from "./PrintApprovedMaterials";
import { applyDocumentLocale, detectBrowserLocale } from "./i18n";
import "./styles.css";
import "./tokens.css";
import "./brand.css";
import "./activity-provenance.css";
import "./print.css";

applyDocumentLocale(detectBrowserLocale());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    <PrintApprovedMaterials />
  </StrictMode>,
);
