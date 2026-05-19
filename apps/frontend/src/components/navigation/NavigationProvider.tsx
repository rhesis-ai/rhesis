'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { type NavigationContextProps } from '../../types/navigation';
import { NavigationItemsContext } from '@/contexts/NavigationItemsContext';

type NavigationProviderProps = NavigationContextProps & {
  children: React.ReactNode;
};

export function NavigationProvider({
  navigation,
  children,
  branding,
}: NavigationProviderProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const contextValue = useMemo(
    () => ({
      navigation: mounted ? navigation : [],
      branding: branding ?? null,
    }),
    [mounted, navigation, branding]
  );

  return (
    <NavigationItemsContext.Provider value={contextValue}>
      {children}
    </NavigationItemsContext.Provider>
  );
}
