'use client';

import { NextAppProvider } from '@toolpad/core/nextjs';
import {
  type NavigationContextProps,
  type NavigationItem,
} from '../../types/navigation';
import { useEffect, useState, useMemo } from 'react';
import { isQuickStartEnabled } from '@/utils/quick_start';

type NavigationProviderProps = NavigationContextProps & {
  children: React.ReactNode;
};

// Transform navigation items to convert links to page items with metadata
function transformNavigationItems(items: NavigationItem[]): any[] {
  return items.map(item => {
    if (item.kind === 'link') {
      // Transform link to a page item with metadata for rendering
      return {
        kind: 'page',
        segment: '', // Empty segment since external links don't need routes
        title: item.title,
        icon: item.icon,
        requireSuperuser: item.requireSuperuser,
        // Store link metadata for renderPageItem to use
        __isExternalLink: true,
        __href: item.href,
        __external: item.external,
      };
    }
    if (item.kind === 'page' && item.children) {
      return {
        ...item,
        children: transformNavigationItems(item.children),
      };
    }
    return item;
  });
}

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

  // Transform navigation to handle link items
  const transformedNavigation = useMemo(() => {
    return transformNavigationItems(navigation);
  }, [navigation]);

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
      navigation={transformedNavigation}
      authentication={filteredAuthentication}
      {...props}
    >
      {children}
    </NextAppProvider>
  );
}
