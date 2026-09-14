import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import PrintApprovedMaterials from "./PrintApprovedMaterials";
import "./tokens.css";
import "./styles.css";
import "./brand.css";
import "./activity-provenance.css";
import "./print.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    <PrintApprovedMaterials />
  </StrictMode>,
);
