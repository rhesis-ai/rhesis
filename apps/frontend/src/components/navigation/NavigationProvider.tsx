'use client';

import { NextAppProvider } from '@toolpad/core/nextjs';
import { type NavigationContextProps } from '../../types/navigation';
import { useEffect, useState } from 'react';
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
  const filteredAuthentication = isQuickStartEnabled() ? null : authentication;

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
