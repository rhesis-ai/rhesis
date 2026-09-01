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
// Module-private: `navCardRowSx` below is the public interface. Exported
// separately once, when NavLinkItem spread it directly; consumers now compose
// the full row instead, so there is one way to build a card row rather than two.
const NAV_CARD_ROW_SX = {
  px: '14px',
  gap: '10px',
} as const;

/** Icon box size for a card row. Module-private: read it through
 * `navCardIconSx`, which is what guarantees every row's gutter matches. */
const NAV_CARD_ICON_SIZE = 24;

/**
 * The complete row shell for a sidebar card row: geometry, hover and
 * transition. Composed by both `NavLinkItem` and `SidebarPlanRow` so every row
 * in a card is the same height and its icon sits in the same gutter.
 *
 * A function rather than a constant because the hover colour and the
 * transition duration are theme reads, and `sx` callbacks cannot be spread out
 * of a plain object without losing them.
 */
export const navCardRowSx = () =>
  ({
    display: 'flex',
    alignItems: 'center',
    ...NAV_CARD_ROW_SX,
    py: '8px',
    borderRadius: BORDER_RADIUS.sm,
    textDecoration: 'none',
    cursor: 'pointer',
    '&:hover': {
      bgcolor: (theme: { palette: { greyscale: { surface1: string } } }) =>
        theme.palette.greyscale.surface1,
    },
    // `duration.shortest` is the theme's own 150ms.
    transition: (theme: {
      transitions: {
        create: (p: string, o: { duration: number }) => string;
        duration: { shortest: number };
      };
    }) =>
      theme.transitions.create('background-color', {
        duration: theme.transitions.duration.shortest,
      }),
  }) as const;

/**
 * The icon gutter. Fixed size and `flexShrink: 0`, which is what puts every
 * row's label on the same x-offset regardless of icon glyph.
 *
 * `color` is deliberately absent: the caller sets it, so a row can tint its
 * icon (the plan crown) without forking the geometry.
 */
export const navCardIconSx = {
  display: 'flex',
  flexShrink: 0,
  '& svg': { width: NAV_CARD_ICON_SIZE, height: NAV_CARD_ICON_SIZE },
} as const;

/**
 * The row label. `minWidth: 0` lets it shrink instead of forcing a trailing
 * element out of the row -- without it a long plan name would push the badge
 * past the row's right padding.
 */
export const navCardLabelSx = {
  fontSize: 14,
  fontWeight: 400,
  lineHeight: '22px',
  whiteSpace: 'nowrap' as const,
  overflow: 'hidden' as const,
  textOverflow: 'ellipsis' as const,
  minWidth: 0,
} as const;

/**
 * A trailing element on a card row -- the plan badge today.
 *
 * `marginLeft: auto` is what anchors it to the row's right padding edge, at
 * the same x for every label and badge length; `flexShrink: 0` is what stops
 * the badge itself being compressed when the label is long.
 */
export const navCardTrailingSx = {
  marginLeft: 'auto',
  flexShrink: 0,
  display: 'flex',
  alignItems: 'center',
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
