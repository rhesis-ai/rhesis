'use client';

import {
  type NavigationItem,
  type NavigationPageItem,
  type NavigationLinkItem,
  type NavigationHeaderItem,
  type NavigationActionItem,
} from '@/types/navigation';
import { BORDER_RADIUS } from '@/styles/theme-constants';

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

/**
 * Horizontal geometry every row inside a sidebar card shares: the side padding
 * and the icon-to-label gap.
 *
 * Named rather than repeated inline because it is an *alignment contract*, not
 * two loose numbers -- the plan row and the link rows below it stack in one
 * card, and their icons and labels have to sit on the same two columns. Typed
 * out separately in each component, they drift the moment one is nudged.
 *
 * Figma values, which is why they are px and not `theme.spacing` units: 14 and
 * 10 are not multiples of the 8px spacing step, so a spacing unit would round
 * them and shift the whole card.
 */
export const NAV_CARD_ROW_SX = {
  px: '14px',
  gap: '10px',
} as const;

/** Icon box for a full-height card row (`NavLinkItem`). */
export const NAV_CARD_ICON_SIZE = 24;

/**
 * A card row that reports state rather than offering an action -- currently
 * the plan row heading the footer card. Tighter vertically so it reads as a
 * status line above the actions instead of a third thing to click, while
 * keeping their horizontal alignment.
 */
export const NAV_CARD_STATUS_ROW_SX = {
  ...NAV_CARD_ROW_SX,
  py: '6px',
} as const;

/**
 * The count-badge pill: a small filled number shown beside something that has
 * a count -- a nav item's unread notifications, the brand row's flagged
 * quota resources, the org and user menu rows.
 *
 * Lives here rather than in `styles/theme-constants.ts` because it is nav
 * chrome, not a design token, and because that file is the token *definition*
 * site: its palette literals are what the hardcoded-styles CI check exists to
 * find everywhere else, so editing it drags all of them into scope.
 *
 * `NavItem` inverts `bgcolor`/`color` on an active row, whose background is
 * already `primary.main`; every other consumer takes this as-is.
 */
export const COUNT_BADGE_SX = {
  minWidth: 20,
  height: 20,
  px: '6px',
  borderRadius: BORDER_RADIUS.sm,
  bgcolor: 'primary.main',
  color: 'primary.contrastText',
  fontSize: 12,
  fontWeight: 600,
  lineHeight: '20px',
  textAlign: 'center',
} as const;

export const collapsedNavGroupSx = {
  alignItems: 'center',
};

// ── Session user type ─────────────────────────────────────────────────────────

export interface ExtendedUser {
  name?: string | null;
  email?: string | null;
  image?: string | null;
}

// ── Active-path helper ────────────────────────────────────────────────────────

export function isActive(pathname: string | null, fullPath: string): boolean {
  if (!pathname) return false;
  return pathname === fullPath || pathname.startsWith(`${fullPath}/`);
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
