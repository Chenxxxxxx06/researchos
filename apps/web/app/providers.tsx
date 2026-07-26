'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

import { I18nProvider } from '@/lib/i18n';
import { ThemeProvider } from '@/lib/theme';
import { Toaster } from '@/components/ui/toast';

/**
 * Client-side providers. TanStack Query owns all server state; I18nProvider
 * owns the interface language; ThemeProvider owns light/dark/system (it sits
 * inside I18nProvider so preference sync-down can adopt the server locale).
 * The Toaster viewport needs i18n and is mounted once here.
 */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 10_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <ThemeProvider>
          {children}
          <Toaster />
        </ThemeProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
