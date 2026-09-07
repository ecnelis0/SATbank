import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

/** Renders inside a fresh QueryClient with retries off, so failures surface at once.
 *
 *  The provider goes in via `wrapper` rather than around the element: RTL's
 *  `rerender` replaces the root element, and a hand-wrapped tree loses the provider
 *  on the second render. */
export function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }

  return { client, ...render(ui, { wrapper: Wrapper }) };
}
