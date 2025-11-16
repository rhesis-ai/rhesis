'use client';

import { NextAppProvider } from '@toolpad/core/nextjs';
import { type NavigationContextProps } from '../../types/navigation';
import { useEffect, useState } from 'react';

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

  // Check if local auth is enabled - if true, pass null authentication to hide logout button
  const isLocalAuthEnabled = process.env.NEXT_PUBLIC_LOCAL_AUTH_ENABLED === 'true';
  
  // Pass null authentication when local auth is enabled to hide account menu
  const filteredAuthentication = isLocalAuthEnabled ? null : authentication;

  // Prevent hydration mismatch by not rendering navigation until client-side
  if (!mounted) {
    return (
      <NextAppProvider navigation={[]} authentication={filteredAuthentication} {...props}>
        {children}
      </NextAppProvider>
    );
  }

  return (
    <NextAppProvider navigation={navigation} authentication={filteredAuthentication} {...props}>
      {children}
    </NextAppProvider>
  );
}
