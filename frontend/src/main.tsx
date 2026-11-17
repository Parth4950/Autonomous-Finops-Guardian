import { StrictMode } from "react";

import { QueryClientProvider } from "@tanstack/react-query";

import { createRoot } from "react-dom/client";

import App from "./App";

import "./index.css";

import { ToastProvider } from "@/components/ui/toast";
import { queryClient } from "@/lib/queryClient";
import { ThemeProvider } from "@/lib/theme";



createRoot(document.getElementById("root")!).render(

  <StrictMode>

    <ThemeProvider>

      <QueryClientProvider client={queryClient}>

        <ToastProvider>

          <App />

        </ToastProvider>

      </QueryClientProvider>

    </ThemeProvider>

  </StrictMode>

);

