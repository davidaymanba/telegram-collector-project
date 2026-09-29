import type { ReactElement, ReactNode } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider, type Lang } from "@/i18n";
import { ThemeProvider } from "@/hooks/use-theme";
import { TooltipProvider } from "@/components/ui/tooltip";

export function renderWithProviders(ui: ReactElement, { lang = "en" as Lang, route = "/" } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <I18nProvider defaultLang={lang}>
        <ThemeProvider>
          <TooltipProvider>
            <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>{children}</MemoryRouter>
          </TooltipProvider>
        </ThemeProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
  return render(ui, { wrapper: Wrapper });
}
