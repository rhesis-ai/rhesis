'use client';

import React, { useState, useContext } from 'react';
import NextLink from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import IconButton from '@mui/material/IconButton';
import Collapse from '@mui/material/Collapse';
import Popover from '@mui/material/Popover';
import SvgIcon from '@mui/material/SvgIcon';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined';
import ExitToAppOutlinedIcon from '@mui/icons-material/ExitToAppOutlined';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import GroupOutlinedIcon from '@mui/icons-material/GroupOutlined';
import { useNavigationItems } from '@/contexts/NavigationItemsContext';
import { useSidebarCollapse } from '@/components/layout/AppShell';
import { UserAvatar } from '@/components/common/UserAvatar';
import { ColorModeContext } from '@/components/providers/ThemeProvider';
import { handleSignOut } from '@/actions/auth';
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
import { GREYSCALE, BORDER_RADIUS, ELEVATION } from '@/styles/theme';

// ── Figma "left_panel_close" / "left_panel_open" SVG icons ──────────────────
// Exact filled path from Figma node 841:38433 (Material Symbols Rounded w300).
// The path uses winding-rule cutouts: the outer rect is filled, the inner
// left-strip and the arrow triangle are counter-clockwise holes so they appear
// as transparent/light against the surrounding dark fill.

const LEFT_PANEL_PATH =
  'M16.048 15.5865V8.4135L12.452 12L16.048 15.5865Z' +
  'M5.30775 20.5C4.80908 20.5 4.38308 20.3234 4.02975 19.9703C3.67658 19.6169 3.5 19.1909 3.5 18.6923V5.30775C3.5 4.80908 3.67658 4.38308 4.02975 4.02975C4.38308 3.67658 4.80908 3.5 5.30775 3.5H18.6923C19.1909 3.5 19.6169 3.67658 19.9703 4.02975C20.3234 4.38308 20.5 4.80908 20.5 5.30775V18.6923C20.5 19.1909 20.3234 19.6169 19.9703 19.9703C19.6169 20.3234 19.1909 20.5 18.6923 20.5H5.30775Z' +
  'M8 19V5H5.30775C5.23075 5 5.16025 5.03208 5.09625 5.09625C5.03208 5.16025 5 5.23075 5 5.30775V18.6923C5 18.7692 5.03208 18.8398 5.09625 18.9038C5.16025 18.9679 5.23075 19 5.30775 19H8Z' +
  'M9.5 19H18.6923C18.7692 19 18.8398 18.9679 18.9038 18.9038C18.9679 18.8398 19 18.7692 19 18.6923V5.30775C19 5.23075 18.9679 5.16025 18.9038 5.09625C18.8398 5.03208 18.7692 5 18.6923 5H9.5V19Z';

function LeftPanelCloseIcon() {
  return (
    <SvgIcon viewBox="0 0 24 24">
      <path d={LEFT_PANEL_PATH} fill="currentColor" />
    </SvgIcon>
  );
}

function LeftPanelOpenIcon() {
  // Mirror horizontally: arrow now points right, indicating "open left panel"
  return (
    <SvgIcon viewBox="0 0 24 24" sx={{ transform: 'scaleX(-1)' }}>
      <path d={LEFT_PANEL_PATH} fill="currentColor" />
    </SvgIcon>
  );
}

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
type StandaloneGroup = { type: 'standalone'; items: NavigationPageItem[] };
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
  const { toggleColorMode, mode } = useContext(ColorModeContext);
  const router = useRouter();

  // Org menu popover
  const [orgMenuAnchor, setOrgMenuAnchor] = useState<HTMLElement | null>(null);
  const orgMenuOpen = Boolean(orgMenuAnchor);

  // User menu popover
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const menuOpen = Boolean(menuAnchor);

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
        transition: 'width 0.2s ease, padding 0.2s ease',
        overflowX: 'hidden',
        boxSizing: 'border-box',
      }}
    >
      {/* ── Top section: brand block + main nav ── */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: '36px',
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          scrollbarWidth: 'none',
          '&::-webkit-scrollbar': { display: 'none' },
        }}
      >
        {/*
         * Brand + toggle area.
         * Collapsed: toggle button on top (centered), logo below.
         * Expanded:  [logo → name → caret] link fills the row, toggle at the right end.
         */}
        {collapsed ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '8px',
              flexShrink: 0,
            }}
          >
            <Tooltip title="Expand sidebar" placement="right">
              <IconButton
                onClick={toggle}
                size="small"
                aria-label="Expand sidebar"
                sx={{
                  p: '6px',
                  borderRadius: BORDER_RADIUS.md,
                  color: theme =>
                    theme.palette.mode === 'light'
                      ? GREYSCALE.light.label
                      : GREYSCALE.dark.label,
                  '&:hover': {
                    bgcolor: theme =>
                      theme.palette.mode === 'light'
                        ? GREYSCALE.light.surface2
                        : GREYSCALE.dark.surface1,
                  },
                }}
              >
                <LeftPanelOpenIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title={orgName} placement="right">
              <Box
                onClick={e => setOrgMenuAnchor(e.currentTarget)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 40,
                  height: 40,
                  flexShrink: 0,
                  cursor: 'pointer',
                  borderRadius: BORDER_RADIUS.md,
                  '&:hover': {
                    bgcolor: theme =>
                      theme.palette.mode === 'light'
                        ? GREYSCALE.light.surface2
                        : GREYSCALE.dark.surface2,
                  },
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
            </Tooltip>
          </Box>
        ) : (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              flexShrink: 0,
            }}
          >
            {/* Brand block: logo + name — opens org menu */}
            <Box
              onClick={e => setOrgMenuAnchor(e.currentTarget)}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                flex: 1,
                minWidth: 0,
                // Reclaim ~2 characters of width (chevron removed) before ellipsis
                mr: '-2ch',
                cursor: 'pointer',
                borderRadius: BORDER_RADIUS.pill,
                '&:hover': {
                  bgcolor: theme =>
                    theme.palette.mode === 'light'
                      ? GREYSCALE.light.surface2
                      : GREYSCALE.dark.surface2,
                },
                transition: 'background-color 0.15s ease',
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
            </Box>
            {/* Collapse toggle — inline, right of brand row */}
            <Tooltip title="Collapse sidebar" placement="right">
              <IconButton
                onClick={toggle}
                size="small"
                aria-label="Collapse sidebar"
                sx={{
                  flexShrink: 0,
                  p: '6px',
                  borderRadius: BORDER_RADIUS.md,
                  color: theme =>
                    theme.palette.mode === 'light'
                      ? GREYSCALE.light.label
                      : GREYSCALE.dark.label,
                  '&:hover': {
                    bgcolor: theme =>
                      theme.palette.mode === 'light'
                        ? GREYSCALE.light.surface2
                        : GREYSCALE.dark.surface1,
                  },
                }}
              >
                <LeftPanelCloseIcon />
              </IconButton>
            </Tooltip>
          </Box>
        )}

        {/* Org menu popover */}
        <Popover
          open={orgMenuOpen}
          anchorEl={orgMenuAnchor}
          onClose={() => setOrgMenuAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
          slotProps={{
            paper: {
              sx: {
                bgcolor: theme =>
                  theme.palette.mode === 'light' ? '#e7e8ec' : '#1a1c20',
                borderRadius: BORDER_RADIUS.lg,
                boxShadow: ELEVATION.xs,
                minWidth: 188,
                py: '10px',
                overflow: 'hidden',
              },
            },
          }}
        >
          <Box
            onClick={() => {
              router.push('/organizations/settings');
              setOrgMenuAnchor(null);
            }}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              px: '14px',
              py: '8px',
              cursor: 'pointer',
              '&:hover': {
                bgcolor: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.border
                    : GREYSCALE.dark.border,
              },
            }}
          >
            <SettingsOutlinedIcon
              sx={{
                fontSize: 24,
                color: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.body
                    : '#ffffff',
              }}
            />
            <Typography
              sx={{
                fontSize: 14,
                fontWeight: 700,
                lineHeight: '22px',
                color: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.body
                    : '#ffffff',
              }}
            >
              Settings
            </Typography>
          </Box>
          <Box
            onClick={() => {
              router.push('/organizations/team');
              setOrgMenuAnchor(null);
            }}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              px: '14px',
              py: '8px',
              cursor: 'pointer',
              '&:hover': {
                bgcolor: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.border
                    : GREYSCALE.dark.border,
              },
            }}
          >
            <GroupOutlinedIcon
              sx={{
                fontSize: 24,
                color: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.body
                    : '#ffffff',
              }}
            />
            <Typography
              sx={{
                fontSize: 14,
                fontWeight: 700,
                lineHeight: '22px',
                color: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.body
                    : '#ffffff',
              }}
            >
              Team
            </Typography>
          </Box>
        </Popover>

        {/* Main nav groups */}
        {mainGroups.map(group => {
          if (group.type === 'standalone') {
            return (
              <Box
                key={`standalone-${group.items.map(i => i.segment).join('-')}`}
                sx={{ display: 'flex', flexDirection: 'column', gap: '6px' }}
              >
                {group.items.map(item => (
                  <NavItem
                    key={`standalone-${item.segment}`}
                    item={item}
                    collapsed={collapsed}
                  />
                ))}
              </Box>
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

        {/* User avatar block — clickable, opens user menu */}
        <Box
          onClick={e => setMenuAnchor(e.currentTarget)}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            px: collapsed ? 0 : '10px',
            py: '10px',
            borderRadius: BORDER_RADIUS.pill,
            overflow: 'hidden',
            cursor: 'pointer',
            '&:hover': {
              bgcolor: theme =>
                theme.palette.mode === 'light'
                  ? GREYSCALE.light.surface2
                  : GREYSCALE.dark.surface2,
            },
            transition: 'background-color 0.15s ease',
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
                    theme.palette.mode === 'light' ? TITLE_COLOR : '#fff',
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

        {/* ── User menu popover (Figma 860:40824) ── */}
        <Popover
          open={menuOpen}
          anchorEl={menuAnchor}
          onClose={() => setMenuAnchor(null)}
          anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
          transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          slotProps={{
            paper: {
              sx: {
                bgcolor: theme =>
                  theme.palette.mode === 'light' ? '#e7e8ec' : '#1a1c20',
                borderRadius: BORDER_RADIUS.lg,
                boxShadow: ELEVATION.xs,
                minWidth: 188,
                py: '10px',
                overflow: 'hidden',
              },
            },
          }}
        >
          {/* Dark Mode */}
          <Box
            onClick={() => {
              toggleColorMode();
              setMenuAnchor(null);
            }}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              px: '14px',
              py: '8px',
              cursor: 'pointer',
              '&:hover': {
                bgcolor: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.border
                    : GREYSCALE.dark.border,
              },
            }}
          >
            <DarkModeOutlinedIcon
              sx={{
                fontSize: 24,
                color: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.body
                    : '#ffffff',
              }}
            />
            <Typography
              sx={{
                fontSize: 14,
                fontWeight: 700,
                lineHeight: '22px',
                color: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.body
                    : '#ffffff',
              }}
            >
              {mode === 'dark' ? 'Light Mode' : 'Dark Mode'}
            </Typography>
          </Box>

          {/* Sign Out */}
          <Box
            onClick={() => handleSignOut()}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              px: '14px',
              py: '8px',
              cursor: 'pointer',
              '&:hover': {
                bgcolor: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.border
                    : GREYSCALE.dark.border,
              },
            }}
          >
            <ExitToAppOutlinedIcon
              sx={{
                fontSize: 24,
                color: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.body
                    : '#ffffff',
              }}
            />
            <Typography
              sx={{
                fontSize: 14,
                fontWeight: 700,
                lineHeight: '22px',
                color: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.body
                    : '#ffffff',
              }}
            >
              Sign Out
            </Typography>
          </Box>
        </Popover>
      </Box>
    </Box>
  );
}
