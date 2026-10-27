'use client';

import React, { useRef, useState } from 'react';
import Box from '@mui/material/Box';
import ButtonBase from '@mui/material/ButtonBase';
import Collapse from '@mui/material/Collapse';
import Typography from '@mui/material/Typography';
import { type Theme } from '@mui/material/styles';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import {
  type NavigationHeaderItem,
  type NavigationPageItem,
} from '@/types/navigation';
import { useAmbientPermissions } from '@/contexts/PermissionsContext';
import { useEndpointConfigured } from '@/hooks/useEndpointConfigured';
import { collapsedNavGroupSx } from './sidebar-utils';
import { NavItem } from './NavItem';

const HEADER_LINE_HEIGHT = '18px';
// Every header row is as tall as the collapse arrow, so pinned bands match.
const HEADER_ROW_HEIGHT = '20px';
// Height of a pinned header's background band; also the step between stacked
// pinned headers.
const headerBandHeight = (theme: Theme) =>
  `calc(${HEADER_ROW_HEIGHT} + ${theme.spacing(1)})`;

interface NavSectionProps {
  header: NavigationHeaderItem;
  items: NavigationPageItem[];
  collapsed: boolean;
  /** How many section headers come after this one; they pin below it. */
  headersBelow?: number;
}

export function NavSection({
  header,
  items,
  collapsed,
  headersBelow = 0,
}: NavSectionProps) {
  const isCollapsible = header.collapsible ?? false;
  const endpointConfigured = useEndpointConfigured(
    header.openUntilEndpointConfigured ?? false
  );
  // Collapsed while the endpoint check loads, so orgs that have one don't see
  // the section flash open then shut.
  const defaultOpen =
    !(header.defaultCollapsed ?? false) ||
    (!!header.openUntilEndpointConfigured && endpointConfigured === false);
  // null until the user toggles; their choice then wins over the default.
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const sectionOpen = userOpen ?? defaultOpen;
  const headerRef = useRef<HTMLButtonElement>(null);
  const itemsRef = useRef<HTMLDivElement>(null);
  // Icon-only sidebar: always show section items (section headers are hidden).
  const showItems = collapsed || !isCollapsible || sectionOpen;
  // Headers pin to the bottom of the scrolling nav, stacked in order, while
  // their section is below the fold, so users can tell the section exists.
  const stickyHeader = !collapsed;
  const [pinned, setPinned] = useState(false);

  const scrollItemsIntoView = () =>
    itemsRef.current?.scrollIntoView?.({
      block: 'nearest',
      behavior: 'smooth',
    });

  // Pinned means the items sit further below than their normal spot right
  // under the header.
  const isPinned = () => {
    const headerEl = headerRef.current;
    const itemsEl = itemsRef.current;
    if (!headerEl || !itemsEl) return false;
    const headerRect = headerEl.getBoundingClientRect();
    return (
      itemsEl.getBoundingClientRect().top >
      headerRect.bottom + headerRect.height
    );
  };

  // A pinned header takes you to its section instead of closing it.
  const handleHeaderClick = () => {
    if (sectionOpen && isPinned()) {
      scrollItemsIntoView();
      return;
    }
    if (isCollapsible) setUserOpen(!sectionOpen);
  };

  // Each NavItem hides itself when its capability is denied. Mirror that
  // decision here (reading the ambient scope set once, not one hook per item)
  // so a section whose every item is hidden doesn't render an orphaned header
  // with an empty body. The membership logic matches `useCan`: fail-closed
  // while loading, permissive when RBAC is off, otherwise a set-membership check.
  const ambient = useAmbientPermissions();
  const hasVisibleItem = items.some(item => {
    const required = item.requiredAnyOf?.length
      ? item.requiredAnyOf
      : item.requiredPermission
        ? [item.requiredPermission]
        : null;
    if (!required) return true;
    if (ambient.loading) return false;
    if (!ambient.enabled) return true;
    return required.some(p => ambient.permitted_actions.includes(p));
  });
  if (!hasVisibleItem) return null;

  return (
    <Box
      sx={
        stickyHeader
          ? // No box of its own, so the header can stick within the whole
            // scrolling nav rather than only within this section.
            { display: 'contents' }
          : {
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--nav-item-gap)',
              ...(collapsed ? collapsedNavGroupSx : {}),
            }
      }
    >
      {!collapsed && (
        <ButtonBase
          ref={headerRef}
          onClick={handleHeaderClick}
          onMouseEnter={() => setPinned(isPinned())}
          tabIndex={isCollapsible ? 0 : -1}
          disableRipple={!isCollapsible}
          sx={{
            ...(stickyHeader && {
              position: 'sticky',
              flexShrink: 0,
              // Each band is one line plus its padding; stack above the ones below.
              bottom: theme =>
                `calc(${headersBelow} * ${headerBandHeight(theme)})`,
              zIndex: 1,
              // Padding gives the pinned header a solid band to cover the items
              // scrolling under it; the negative margin keeps the layout as is.
              py: 0.5,
              my: -0.5,
              bgcolor: theme => theme.palette.greyscale.surface1,
              // Reach up over the band above: bands that merely touch leave a
              // see-through hairline at fractional zoom levels.
              '&::before': {
                content: '""',
                position: 'absolute',
                left: 0,
                right: 0,
                bottom: '100%',
                height: theme => theme.spacing(0.25),
                bgcolor: theme => theme.palette.greyscale.surface1,
              },
            }),
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            // Border-box, so the band height includes the padding.
            ...(stickyHeader && { height: headerBandHeight }),
            px: '14px',
            width: '100%',
            cursor: isCollapsible || pinned ? 'pointer' : 'default',
            userSelect: 'none',
          }}
        >
          <Typography
            sx={{
              fontSize: 12,
              fontWeight: 600,
              lineHeight: HEADER_LINE_HEIGHT,
              color: theme => theme.palette.greyscale.subtitle,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            {header.title}
          </Typography>
          {isCollapsible && (
            <Box
              sx={{
                color: theme => theme.palette.greyscale.subtitle,
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {sectionOpen ? (
                <KeyboardArrowUpIcon sx={{ fontSize: 20 }} />
              ) : (
                <KeyboardArrowDownIcon sx={{ fontSize: 20 }} />
              )}
            </Box>
          )}
        </ButtonBase>
      )}

      {/* Items — always visible when sidebar is collapsed, not collapsible, or toggled open */}
      {/* Sections near the bottom open below the fold, and users don't
          notice the nav scrolls -- bring the opened items into view. Only on
          a user toggle, never for a section that starts open. */}
      <Collapse
        in={showItems}
        timeout="auto"
        onEntered={() => {
          if (userOpen) scrollItemsIntoView();
        }}
        // The parent has no box when the header is sticky, so this sits in the
        // nav's own flex column: restore the header-to-items gap the parent's
        // gap used to give, and don't let a short window squash it (Collapse's
        // overflow: hidden lets flex shrink it).
        sx={
          stickyHeader
            ? {
                flexShrink: 0,
                mt: 'calc(var(--nav-item-gap) - var(--nav-group-gap))',
              }
            : undefined
        }
      >
        <Box
          ref={itemsRef}
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--nav-item-gap)',
            ...(collapsed ? collapsedNavGroupSx : {}),
            // Keep scrolled-to items clear of the headers pinned below them.
            scrollMarginBottom: theme =>
              `calc(${headersBelow} * ${headerBandHeight(theme)})`,
          }}
        >
          {items.map(item => (
            <NavItem key={item.segment} item={item} collapsed={collapsed} />
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

export default NavSection;
