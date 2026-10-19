import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./app";
import { AppProvider } from "./lib/store";
import { Toaster } from "./lib/toast";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AppProvider>
      <App />
      <Toaster />
    </AppProvider>
  </StrictMode>
);
