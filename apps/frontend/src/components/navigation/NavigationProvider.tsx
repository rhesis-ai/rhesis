'use client';

import { NextAppProvider } from '@toolpad/core/nextjs';
import {
  type NavigationContextProps,
  type NavigationItem,
} from '../../types/navigation';
import { useEffect, useState, useMemo, useCallback } from 'react';
import { isQuickStartEnabled } from '@/utils/quick_start';
import { useRouter, usePathname } from 'next/navigation';

type NavigationProviderProps = NavigationContextProps & {
  children: React.ReactNode;
};

// Browser-safe base64 encoding
function encodeBase64(str: string): string {
  if (typeof window !== 'undefined') {
    return btoa(encodeURIComponent(str)).replace(/[=/+]/g, '_');
  }
  return str.replace(/[^a-zA-Z0-9]/g, '_');
}

// Browser-safe base64 decoding
function decodeBase64(str: string): string {
  if (typeof window !== 'undefined') {
    try {
      return decodeURIComponent(atob(str.replace(/_/g, '=')));
    } catch (e) {
      return '';
    }
  }
  return '';
}

// Transform navigation items to handle links
function transformNavigationItems(items: NavigationItem[]): any[] {
  return items.map(item => {
    if (item.kind === 'link') {
      // Transform link to a page item with special segment
      return {
        kind: 'page',
        segment: `__link__${encodeBase64(item.href)}`,
        title: item.title,
        icon: item.icon,
        requireSuperuser: item.requireSuperuser,
        __isLink: true,
        __linkHref: item.href,
        __linkExternal: item.external,
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
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    setMounted(true);
  }, []);

  // Transform navigation to handle links and actions
  const transformedNavigation = useMemo(() => {
    return transformNavigationItems(navigation);
  }, [navigation]);

  // Intercept navigation to handle links and actions
  useEffect(() => {
    if (!mounted || !pathname) return;

    // Check if we're navigating to a link or action segment
    if (pathname.startsWith('/__link__')) {
      // Extract the base64 encoded URL
      const encodedUrl = pathname.replace('/__link__', '');
      const href = decodeBase64(encodedUrl);

      if (href) {
        const navItem = navigation.find(
          item => item.kind === 'link' && item.href === href
        );
        if (navItem && navItem.kind === 'link') {
          if (navItem.external) {
            // Open in new tab
            window.open(navItem.href, '_blank', 'noopener,noreferrer');
            // Navigate back after a short delay to ensure window.open completes
            setTimeout(() => {
              router.back();
            }, 100);
          } else {
            router.push(navItem.href);
          }
        } else {
          router.back();
        }
      } else {
        router.back();
      }
    }
  }, [pathname, navigation, router, mounted]);

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
