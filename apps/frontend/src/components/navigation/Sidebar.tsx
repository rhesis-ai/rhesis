'use client';

import React, { useState } from 'react';
import NextLink from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { useSession } from 'next-auth/react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import IconButton from '@mui/material/IconButton';
import Collapse from '@mui/material/Collapse';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useNavigationItems } from '@/contexts/NavigationItemsContext';
import { useSidebarCollapse } from '@/components/layout/AppShell';
import { UserAvatar } from '@/components/common/UserAvatar';
import {
  SIDEBAR_WIDTH,
  SIDEBAR_COLLAPSED_WIDTH,
} from '@/components/layout/sidebar-constants';
import {
  type NavigationItem,
  type NavigationPageItem,
  type NavigationLinkItem,
  type NavigationHeaderItem,
} from '@/types/navigation';
import { GREYSCALE, BORDER_RADIUS } from '@/styles/theme';

// Figma design tokens (resolved from theme constants — no raw hex in this file)
const NAV_BG_LIGHT = GREYSCALE.light.surface1;
const NAV_BG_DARK = GREYSCALE.dark.surface1;
const TITLE_COLOR = GREYSCALE.light.title;
const BODY_COLOR = GREYSCALE.light.body;
const SUBTITLE_COLOR = GREYSCALE.light.subtitle;

interface ExtendedUser {
  name?: string | null;
  email?: string | null;
  image?: string | null;
  is_superuser?: boolean;
}

function isActive(pathname: string | null, fullPath: string): boolean {
  if (!pathname) return false;
  return pathname === fullPath || pathname.startsWith(`${fullPath}/`);
}

function filterNavItems(
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

// Group flat navigation array into typed sections for Figma-aligned rendering
type StandaloneGroup = { type: 'standalone'; item: NavigationPageItem };
type SectionGroup = {
  type: 'section';
  header: NavigationHeaderItem;
  items: NavigationPageItem[];
};
type FooterLinksGroup = { type: 'footer-links'; items: NavigationLinkItem[] };
type NavGroup = StandaloneGroup | SectionGroup | FooterLinksGroup;

function groupNavItems(items: NavigationItem[]): NavGroup[] {
  const groups: NavGroup[] = [];
  let currentSection: {
    header: NavigationHeaderItem;
    items: NavigationPageItem[];
  } | null = null;
  const footerLinks: NavigationLinkItem[] = [];
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
      if (item.kind === 'link') footerLinks.push(item);
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
        groups.push({ type: 'standalone', item });
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

// ─── NavItem ────────────────────────────────────────────────────────────────

interface NavItemProps {
  item: NavigationPageItem;
  collapsed: boolean;
  parentPath?: string;
}

function NavItem({ item, collapsed, parentPath = '' }: NavItemProps) {
  const pathname = usePathname();
  const fullPath = parentPath
    ? `${parentPath}/${item.segment}`
    : `/${item.segment}`;
  const active = isActive(pathname, fullPath);

  const button = (
    <Box
      component={NextLink}
      href={fullPath}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        px: '14px',
        py: '8px',
        borderRadius: BORDER_RADIUS.sm,
        textDecoration: 'none',
        cursor: 'pointer',
        bgcolor: active ? 'primary.dark' : 'transparent',
        '&:hover': {
          bgcolor: active
            ? 'primary.dark'
            : theme =>
                theme.palette.mode === 'light'
                  ? GREYSCALE.light.surface1
                  : GREYSCALE.dark.surface1,
        },
        transition: 'background-color 0.15s ease',
      }}
    >
      {item.icon && (
        <Box
          sx={{
            display: 'flex',
            flexShrink: 0,
            color: active
              ? '#fff'
              : theme =>
                  theme.palette.mode === 'light'
                    ? BODY_COLOR
                    : GREYSCALE.dark.body,
            '& svg': { width: 24, height: 24 },
          }}
        >
          {item.icon}
        </Box>
      )}
      {!collapsed && (
        <>
          <Typography
            sx={{
              fontSize: 14,
              fontWeight: active ? 600 : 400,
              lineHeight: '22px',
              color: active
                ? '#fff'
                : theme =>
                    theme.palette.mode === 'light'
                      ? BODY_COLOR
                      : GREYSCALE.dark.body,
              whiteSpace: 'nowrap',
              flex: 1,
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {item.title}
          </Typography>
          {item.action && <Box sx={{ flexShrink: 0 }}>{item.action}</Box>}
        </>
      )}
    </Box>
  );

  return collapsed ? (
    <Tooltip title={item.title} placement="right">
      {button}
    </Tooltip>
  ) : (
    button
  );
}

// ─── NavLinkItem ─────────────────────────────────────────────────────────────

interface NavLinkItemProps {
  item: NavigationLinkItem;
  collapsed: boolean;
}

function NavLinkItem({ item, collapsed }: NavLinkItemProps) {
  const button = (
    <Box
      component="a"
      href={item.href}
      target={item.external ? '_blank' : undefined}
      rel={item.external ? 'noopener noreferrer' : undefined}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        px: '14px',
        py: '8px',
        borderRadius: BORDER_RADIUS.sm,
        textDecoration: 'none',
        cursor: 'pointer',
        '&:hover': {
          bgcolor: theme =>
            theme.palette.mode === 'light'
              ? GREYSCALE.light.surface1
              : GREYSCALE.dark.surface1,
        },
        transition: 'background-color 0.15s ease',
      }}
    >
      {item.icon && (
        <Box
          sx={{
            display: 'flex',
            flexShrink: 0,
            color: theme =>
              theme.palette.mode === 'light' ? BODY_COLOR : GREYSCALE.dark.body,
            '& svg': { width: 24, height: 24 },
          }}
        >
          {item.icon}
        </Box>
      )}
      {!collapsed && (
        <>
          <Typography
            sx={{
              fontSize: 14,
              fontWeight: 400,
              lineHeight: '22px',
              color: theme =>
                theme.palette.mode === 'light'
                  ? BODY_COLOR
                  : GREYSCALE.dark.body,
              whiteSpace: 'nowrap',
              flex: 1,
            }}
          >
            {item.title}
          </Typography>
          {item.external && (
            <OpenInNewIcon
              sx={{ fontSize: 14, color: SUBTITLE_COLOR, flexShrink: 0 }}
            />
          )}
        </>
      )}
    </Box>
  );

  return collapsed ? (
    <Tooltip title={item.title} placement="right">
      {button}
    </Tooltip>
  ) : (
    button
  );
}

// ─── NavSection ──────────────────────────────────────────────────────────────

interface NavSectionProps {
  header: NavigationHeaderItem;
  items: NavigationPageItem[];
  collapsed: boolean;
}

function NavSection({ header, items, collapsed }: NavSectionProps) {
  const isCollapsible = header.collapsible ?? false;
  const [sectionOpen, setSectionOpen] = useState(
    !(header.defaultCollapsed ?? false)
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {!collapsed && (
        <Box
          onClick={isCollapsible ? () => setSectionOpen(o => !o) : undefined}
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: '14px',
            cursor: isCollapsible ? 'pointer' : 'default',
            userSelect: 'none',
          }}
        >
          <Typography
            sx={{
              fontSize: 12,
              fontWeight: 600,
              lineHeight: '18px',
              color: SUBTITLE_COLOR,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            {header.title}
          </Typography>
          {isCollapsible && (
            <Box
              sx={{
                color: SUBTITLE_COLOR,
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
        </Box>
      )}

      {/* Items — always visible when sidebar is not collapsible, or toggled when collapsible */}
      <Collapse in={!isCollapsible || sectionOpen} timeout="auto">
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {items.map(item => (
            <NavItem key={item.segment} item={item} collapsed={collapsed} />
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

// ─── Sidebar ─────────────────────────────────────────────────────────────────

export function Sidebar() {
  const { navigation, branding } = useNavigationItems();
  const { collapsed, toggle } = useSidebarCollapse();
  const { data: session } = useSession();
  const user = session?.user as ExtendedUser | undefined;

  const orgName = branding?.title ?? 'Rhesis AI';
  const isSuperuser = user?.is_superuser === true;
  const filteredNavigation = filterNavItems(navigation, isSuperuser);
  const groups = groupNavItems(filteredNavigation);

  const mainGroups = groups.filter(g => g.type !== 'footer-links') as (
    | StandaloneGroup
    | SectionGroup
  )[];
  const footerGroup = groups.find(g => g.type === 'footer-links') as
    | FooterLinksGroup
    | undefined;

  const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH;

  return (
    <Box
      sx={{
        width: sidebarWidth,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        bgcolor: theme =>
          theme.palette.mode === 'light' ? NAV_BG_LIGHT : NAV_BG_DARK,
        px: collapsed ? '12px' : '26px',
        py: '30px',
        position: 'relative',
        transition: 'width 0.2s ease, padding 0.2s ease',
        overflow: 'visible',
        boxSizing: 'border-box',
      }}
    >
      {/* Collapse toggle — absolute-positioned just outside the sidebar right edge */}
      <Tooltip
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        placement="right"
      >
        <IconButton
          onClick={toggle}
          size="small"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          sx={{
            position: 'absolute',
            top: 0,
            right: -16,
            zIndex: 10,
            width: 28,
            height: 48,
            borderTopRightRadius: BORDER_RADIUS.sm,
            borderBottomRightRadius: BORDER_RADIUS.sm,
            bgcolor: theme =>
              theme.palette.mode === 'light' ? NAV_BG_LIGHT : NAV_BG_DARK,
            border: theme =>
              `1px solid ${theme.palette.mode === 'light' ? GREYSCALE.light.border : GREYSCALE.dark.border}`,
            borderLeft: 'none',
            '&:hover': {
              bgcolor: theme =>
                theme.palette.mode === 'light'
                  ? GREYSCALE.light.surface1
                  : GREYSCALE.dark.surface1,
            },
          }}
        >
          {collapsed ? (
            <ChevronRightIcon sx={{ fontSize: 16 }} />
          ) : (
            <ChevronLeftIcon sx={{ fontSize: 16 }} />
          )}
        </IconButton>
      </Tooltip>

      {/* ── Top section: brand block + main nav ── */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: '36px',
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          // hide scrollbar visually
          scrollbarWidth: 'none',
          '&::-webkit-scrollbar': { display: 'none' },
        }}
      >
        {/* Brand block: logo icon + org name + caret */}
        <Box
          component={NextLink}
          href="/organizations"
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            textDecoration: 'none',
            flexShrink: 0,
            '&:hover': { opacity: 0.85 },
          }}
        >
          <Box
            sx={{
              width: 40,
              height: 40,
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Image
              src="/logos/rhesis-logo-favicon.svg"
              alt="Rhesis logo"
              width={40}
              height={40}
              priority
            />
          </Box>
          {!collapsed && (
            <>
              <Typography
                sx={{
                  fontSize: 18,
                  fontWeight: 700,
                  lineHeight: '25px',
                  color: theme =>
                    theme.palette.mode === 'light' ? TITLE_COLOR : '#ffffff',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  flex: 1,
                  minWidth: 0,
                }}
              >
                {orgName}
              </Typography>
              <KeyboardArrowDownIcon
                sx={{ fontSize: 20, color: SUBTITLE_COLOR, flexShrink: 0 }}
              />
            </>
          )}
        </Box>

        {/* Main nav groups */}
        {mainGroups.map(group => {
          if (group.type === 'standalone') {
            return (
              <NavItem
                key={`standalone-${group.item.segment}`}
                item={group.item}
                collapsed={collapsed}
              />
            );
          }
          return (
            <NavSection
              key={`section-${group.header.title}`}
              header={group.header}
              items={group.items}
              collapsed={collapsed}
            />
          );
        })}
      </Box>

      {/* ── Bottom section: footer link card + user avatar ── */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
          flexShrink: 0,
          pt: '20px',
        }}
      >
        {/* White rounded card for external footer links (Star Rhesis, Support) */}
        {footerGroup && footerGroup.items.length > 0 && (
          <Box
            sx={{
              bgcolor: theme =>
                theme.palette.mode === 'light' ? '#ffffff' : '#1F242B',
              borderRadius: BORDER_RADIUS.lg,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {footerGroup.items.map(item => (
              <NavLinkItem
                key={`footer-${item.title}`}
                item={item}
                collapsed={collapsed}
              />
            ))}
          </Box>
        )}

        {/* User avatar block */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            px: collapsed ? 0 : '10px',
            py: '10px',
            borderRadius: BORDER_RADIUS.pill,
            overflow: 'hidden',
          }}
        >
          <UserAvatar
            userName={user?.name ?? undefined}
            userPicture={user?.image ?? undefined}
            size={32}
            sx={{ flexShrink: 0 }}
          />
          {!collapsed && (
            <Box sx={{ minWidth: 0 }}>
              <Typography
                sx={{
                  display: 'block',
                  fontSize: 14,
                  fontWeight: 400,
                  lineHeight: '22px',
                  color: theme =>
                    theme.palette.mode === 'light' ? TITLE_COLOR : '#ffffff',
                  textDecoration: 'underline',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {user?.name ?? 'User'}
              </Typography>
              <Typography
                sx={{
                  display: 'block',
                  fontSize: 12,
                  fontWeight: 400,
                  lineHeight: '18px',
                  color: SUBTITLE_COLOR,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {user?.email ?? ''}
              </Typography>
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
}
