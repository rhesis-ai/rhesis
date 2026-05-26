'use client';

import React from 'react';
import { type NavigationItem, type BrandingProps } from '../types/navigation';

interface NavigationItemsContextValue {
  navigation: NavigationItem[];
  branding: BrandingProps | null;
}

export const NavigationItemsContext =
  React.createContext<NavigationItemsContextValue>({
    navigation: [],
    branding: null,
  });

export function useNavigationItems() {
  return React.useContext(NavigationItemsContext);
}
