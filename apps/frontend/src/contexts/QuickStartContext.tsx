'use client';

import * as React from 'react';

const QuickStartContext = React.createContext<boolean>(false);

/**
 * Provides the Quick Start mode flag app-wide from a single server-fetched
 * value (see `fetchQuickStartEnabledServer` in `@/utils/quick_start`),
 * seeded once in the root layout. Consumers (`TermsAcceptanceGate`, the
 * landing page, etc.) read it via `useQuickStart()` instead of each making
 * their own `GET /api/auth-config` call on mount — which was the source of
 * duplicate auth-config requests on every page load.
 */
export function QuickStartProvider({
  value,
  children,
}: {
  value: boolean;
  children: React.ReactNode;
}) {
  return (
    <QuickStartContext.Provider value={value}>
      {children}
    </QuickStartContext.Provider>
  );
}

export function useQuickStart(): boolean {
  return React.useContext(QuickStartContext);
}
