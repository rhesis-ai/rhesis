'use client';

import {
  type NavigationItem,
  type NavigationPageItem,
  type NavigationLinkItem,
  type NavigationHeaderItem,
  type NavigationActionItem,
} from '@/types/navigation';
import type { Theme } from '@mui/material/styles';
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
 * them and shift the whole card. The vertical padding in `navCardRowSx` *is* on
 * the step, so it uses the spacing scale.
 */
// Module-private: `navCardRowSx` below is the public interface. Exported
// separately once, when NavLinkItem spread it directly; consumers now compose
// the full row instead, so there is one way to build a card row rather than two.
const NAV_CARD_ROW_SX = {
  px: '14px',
  gap: '10px',
} as const;

/** The icon-to-label gap, exported for a row that builds its own inner flex
 * line (the plan row's crown + badge) and must land on the same x as the
 * single-line rows' labels. Same value `navCardRowSx` uses, not a copy. */
export const NAV_CARD_ICON_GAP = NAV_CARD_ROW_SX.gap;

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
 *
 * Pass `interactive: false` for a row that only reports state. It keeps the
 * geometry -- which is the whole point of sharing this -- and drops the pointer
 * cursor and hover tint, so a static row does not read as a broken link beside
 * the actionable ones. The alternative, a bespoke layout for the static row, is
 * what made the plan row's label start at a different x-offset in the first
 * place.
 */
export const navCardRowSx = ({ interactive = true } = {}) =>
  ({
    display: 'flex',
    alignItems: 'center',
    ...NAV_CARD_ROW_SX,
    py: 1,
    borderRadius: BORDER_RADIUS.sm,
    textDecoration: 'none',
    ...(interactive
      ? {
          cursor: 'pointer',
          '&:hover': {
            bgcolor: (theme: {
              palette: { greyscale: { surface1: string } };
            }) => theme.palette.greyscale.surface1,
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
        }
      : {}),
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
 * The row label's *geometry* only. `minWidth: 0` lets it shrink instead of
 * forcing a trailing element out of the row -- without it a long plan name
 * would push the badge past the row's right padding.
 *
 * Type is deliberately absent: consumers pass `variant="bodyMReg"` on the
 * `Typography` instead. That variant is exactly this row's type (400 / 14px /
 * 22px), and reading it from the theme rather than restating the three numbers
 * matters for the same reason the badge's weight does -- the theme's weights
 * shift on a branded deployment, so a literal would silently stop matching the
 * rest of the sidebar.
 */
export const navCardLabelSx = {
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
  // Type from the theme, not literals. `600` was a real bug, not just a
  // convention slip: the theme's semibold is 700 when a brand font is
  // configured, so the literal rendered this badge lighter than every other
  // semibold element on a branded deployment.
  fontSize: (theme: Theme) => theme.typography.captionBold.fontSize,
  fontWeight: (theme: Theme) => theme.typography.captionBold.fontWeight,
  // Geometry, deliberately not from the variant: this matches the badge's own
  // 20px height so the number sits centred, where `captionBold`'s 18px would
  // not.
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
