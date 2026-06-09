'use client';

import {
  type NavigationItem,
  type NavigationPageItem,
  type NavigationLinkItem,
  type NavigationHeaderItem,
  type NavigationActionItem,
} from '@/types/navigation';

// ── Shared nav sizing constants ───────────────────────────────────────────────

/** 40×40 icon hit target inside the 64px collapsed sidebar (12px rail padding each side). */
export const COLLAPSED_NAV_ITEM_SIZE = 40;

export const collapsedNavItemSx = {
  justifyContent: 'center',
  gap: 0,
  p: '8px',
  width: COLLAPSED_NAV_ITEM_SIZE,
  height: COLLAPSED_NAV_ITEM_SIZE,
  boxSizing: 'border-box' as const,
  alignSelf: 'center',
};

export const collapsedNavGroupSx = {
  alignItems: 'center',
};

// ── Session user type ─────────────────────────────────────────────────────────

export interface ExtendedUser {
  name?: string | null;
  email?: string | null;
  image?: string | null;
  is_superuser?: boolean;
}

// ── Active-path helper ────────────────────────────────────────────────────────

export function isActive(pathname: string | null, fullPath: string): boolean {
  if (!pathname) return false;
  return pathname === fullPath || pathname.startsWith(`${fullPath}/`);
}

// ── Navigation filtering ──────────────────────────────────────────────────────

export function filterNavItems(
  items: NavigationItem[],
  isSuperuser: boolean
): NavigationItem[] {
  return items.reduce<NavigationItem[]>((acc, item) => {
    const needsSuperuser =
      'requireSuperuser' in item &&
      (item as { requireSuperuser?: boolean }).requireSuperuser;
    if (needsSuperuser && !isSuperuser) return acc;
    if (item.kind === 'page' && item.children && item.children.length > 0) {
      acc.push({
        ...item,
        children: filterNavItems(item.children, isSuperuser),
      } as NavigationPageItem);
    } else {
      acc.push(item);
    }
    return acc;
  }, []);
}

// ── Navigation grouping ───────────────────────────────────────────────────────

export type StandaloneGroup = {
  type: 'standalone';
  items: NavigationPageItem[];
};
export type SectionGroup = {
  type: 'section';
  header: NavigationHeaderItem;
  items: NavigationPageItem[];
};
export type FooterLinksGroup = {
  type: 'footer-links';
  items: (NavigationLinkItem | NavigationActionItem)[];
};
export type NavGroup = StandaloneGroup | SectionGroup | FooterLinksGroup;

export function groupNavItems(items: NavigationItem[]): NavGroup[] {
  const groups: NavGroup[] = [];
  let currentSection: {
    header: NavigationHeaderItem;
    items: NavigationPageItem[];
  } | null = null;
  const footerLinks: (NavigationLinkItem | NavigationActionItem)[] = [];
  let inFooter = false;

  for (const item of items) {
    if (item.kind === 'divider') {
      if (currentSection) {
        groups.push({
          type: 'section',
          header: currentSection.header,
          items: currentSection.items,
        });
        currentSection = null;
      }
      inFooter = true;
      continue;
    }
    if (inFooter) {
      if (item.kind === 'link' || item.kind === 'action')
        footerLinks.push(item);
      continue;
    }
    if (item.kind === 'header') {
      if (currentSection) {
        groups.push({
          type: 'section',
          header: currentSection.header,
          items: currentSection.items,
        });
      }
      currentSection = { header: item, items: [] };
    } else if (item.kind === 'page') {
      if (currentSection) {
        currentSection.items.push(item);
      } else {
        const last = groups[groups.length - 1];
        if (last?.type === 'standalone') {
          last.items.push(item);
        } else {
          groups.push({ type: 'standalone', items: [item] });
        }
      }
    }
  }

  if (currentSection) {
    groups.push({
      type: 'section',
      header: currentSection.header,
      items: currentSection.items,
    });
  }
  if (footerLinks.length > 0) {
    groups.push({ type: 'footer-links', items: footerLinks });
  }

  return groups;
}
