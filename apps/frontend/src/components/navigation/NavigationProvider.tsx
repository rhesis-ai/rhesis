'use client';

import React, { useMemo } from 'react';
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
  const contextValue = useMemo(
    () => ({
      navigation,
      branding: branding ?? null,
    }),
    [navigation, branding]
  );

  return (
    <NavigationItemsContext.Provider value={contextValue}>
      {children}
    </NavigationItemsContext.Provider>
  );
}
