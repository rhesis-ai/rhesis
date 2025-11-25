'use client';

import { NextAppProvider } from '@toolpad/core/nextjs';
import { type NavigationContextProps } from '../../types/navigation';
import { useEffect, useState, useMemo } from 'react';
import { isQuickStartEnabled } from '@/utils/quick_start';

type NavigationProviderProps = NavigationContextProps & {
  children: React.ReactNode;
};

export function NavigationProvider({
  navigation,
  children,
  authentication,
  ...props
}: NavigationProviderProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Use robust multi-factor detection to determine if Quick Start mode is enabled
  // Pass null authentication when Quick Start is enabled to hide account menu
  // SECURITY: Defer computation until after client-side mount to ensure hostname validation
  // During SSR, window is undefined and hostname checks are skipped, which could allow
  // Quick Start mode in cloud deployments if NEXT_PUBLIC_QUICK_START is misconfigured.
  const filteredAuthentication = useMemo(() => {
    // Fail-secure: Don't compute until mounted (client-side) to ensure hostname validation
    if (!mounted) {
      return authentication;
    }
    return isQuickStartEnabled() ? null : authentication;
  }, [mounted, authentication]);

  // Prevent hydration mismatch by not rendering navigation until client-side
  if (!mounted) {
    return (
      <NextAppProvider
        navigation={[]}
        authentication={filteredAuthentication}
        {...props}
      >
        {children}
      </NextAppProvider>
    );
  }

  return (
    <NextAppProvider
      navigation={navigation}
      authentication={filteredAuthentication}
      {...props}
    >
      {children}
    </NextAppProvider>
  );
}
