import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import PrintApprovedMaterials from "./PrintApprovedMaterials";
import "./styles.css";
import "./brand.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    <PrintApprovedMaterials />
  </StrictMode>,
);
