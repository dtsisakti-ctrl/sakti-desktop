import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { selectStore } from "../api/client";
import { PortalApp } from "./PortalApp";
import "../styles/app.css";
import "../styles/portal.css";

// The candidate session never mixes with a staff session in the same browser. Modules read the
// token only when a request is made, so selecting the store here (after imports) is early enough.
selectStore("eg.portal");

createRoot(document.getElementById("root")!).render(<StrictMode><PortalApp /></StrictMode>);
