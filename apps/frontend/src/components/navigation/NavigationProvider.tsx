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
  ...props
}: NavigationProviderProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Prevent hydration mismatch by not rendering navigation until client-side
  if (!mounted) {
    return (
      <NextAppProvider navigation={[]} {...props}>
        {children}
      </NextAppProvider>
    );
  }

  return (
    <NextAppProvider navigation={navigation} {...props}>
      {children}
    </NextAppProvider>
  );
}
