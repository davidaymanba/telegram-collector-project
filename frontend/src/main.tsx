import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { I18nProvider, useI18n } from "@/i18n";
import { ThemeProvider, useTheme } from "@/hooks/use-theme";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ApiError } from "@/lib/api";
import App from "./App";
import "./styles/globals.css";

const queryClient = new QueryClient({
  queryCache: new QueryCache(),
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: true,
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
    },
  },
});

function ThemedToaster() {
  const { resolved } = useTheme();
  const { dir } = useI18n();
  return (
    <Toaster
      theme={resolved}
      dir={dir}
      position={dir === "rtl" ? "bottom-left" : "bottom-right"}
      closeButton
      toastOptions={{ classNames: { toast: "font-sans !rounded-lg !border !text-sm" } }}
    />
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <ThemeProvider>
          <TooltipProvider delayDuration={250}>
            <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
              <App />
            </BrowserRouter>
            <ThemedToaster />
          </TooltipProvider>
        </ThemeProvider>
      </I18nProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
