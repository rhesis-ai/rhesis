'use client';

import React, { createContext, useContext, useMemo } from 'react';
import { type NavigationItem, type BrandingProps } from '@/types/navigation';

interface NavigationContextValue {
  navigation: NavigationItem[];
  branding: BrandingProps;
}

const NavigationContext = createContext<NavigationContextValue>({
  navigation: [],
  branding: { title: '', logo: null },
});

export function useNavigation() {
  return useContext(NavigationContext);
}

interface NavigationContextProviderProps {
  navigation: NavigationItem[];
  branding: BrandingProps;
  children: React.ReactNode;
}

export function NavigationContextProvider({
  navigation,
  branding,
  children,
}: NavigationContextProviderProps) {
  const value = useMemo(
    () => ({ navigation, branding }),
    [navigation, branding]
  );

  return (
    <NavigationContext.Provider value={value}>
      {children}
    </NavigationContext.Provider>
  );
}
