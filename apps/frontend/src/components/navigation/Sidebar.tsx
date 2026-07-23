'use client';

import React, { useState, useContext } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import Box from '@mui/material/Box';
import ButtonBase from '@mui/material/ButtonBase';
import MenuItem from '@mui/material/MenuItem';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import IconButton from '@mui/material/IconButton';
import Popover from '@mui/material/Popover';
import SvgIcon from '@mui/material/SvgIcon';
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined';
import ExitToAppOutlinedIcon from '@mui/icons-material/ExitToAppOutlined';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import AppsOutlinedIcon from '@mui/icons-material/AppsOutlined';
import SwapHorizOutlinedIcon from '@mui/icons-material/SwapHorizOutlined';
import Divider from '@mui/material/Divider';
import { useNavigationItems } from '@/contexts/NavigationItemsContext';
import { useSidebarCollapse } from '@/components/layout/AppShell';
import { UserAvatar } from '@/components/common/UserAvatar';
import { ColorModeContext } from '@/components/providers/ThemeProvider';
import { handleSignOut } from '@/actions/auth';
import {
  SIDEBAR_WIDTH,
  SIDEBAR_COLLAPSED_WIDTH,
} from '@/components/layout/sidebar-constants';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import {
  type ExtendedUser,
  type StandaloneGroup,
  type SectionGroup,
  type FooterLinksGroup,
  groupNavItems,
  collapsedNavGroupSx,
  COLLAPSED_NAV_ITEM_SIZE,
} from './sidebar-utils';
import { NavItem } from './NavItem';
import { NavLinkItem } from './NavLinkItem';
import { NavSection } from './NavSection';
import ProjectSwitcherDrawer from './ProjectSwitcherDrawer';
import SupportDrawer from './SupportDrawer';
import { useActiveProject } from '@/contexts/ActiveProjectContext';

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

  // Project switcher drawer
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const { activeProject } = useActiveProject();

  // Support drawer
  const [supportOpen, setSupportOpen] = useState(false);

  const orgName = branding?.title ?? 'Rhesis AI';
  const groups = groupNavItems(navigation);

  const mainGroups = groups.filter(g => g.type !== 'footer-links') as (
    StandaloneGroup | SectionGroup
  )[];
  const footerGroup = groups.find(g => g.type === 'footer-links') as
    FooterLinksGroup | undefined;

  const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH;

  return (
    <Box
      sx={{
        width: sidebarWidth,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        bgcolor: theme => theme.palette.greyscale.surface1,
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
          gap: '28px',
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
                  color: theme => theme.palette.greyscale.label,
                  '&:hover': {
                    bgcolor: theme => theme.palette.greyscale.surface2,
                  },
                }}
              >
                <LeftPanelOpenIcon />
              </IconButton>
            </Tooltip>
            <Tooltip
              title={
                activeProject ? `${orgName} · ${activeProject.name}` : orgName
              }
              placement="right"
            >
              <ButtonBase
                onClick={e => setOrgMenuAnchor(e.currentTarget)}
                aria-label={`Open organisation menu for ${orgName}`}
                aria-haspopup="true"
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 40,
                  height: 40,
                  flexShrink: 0,
                  borderRadius: BORDER_RADIUS.md,
                  '&:hover': {
                    bgcolor: theme => theme.palette.greyscale.surface2,
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
              </ButtonBase>
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
            <ButtonBase
              onClick={e => setOrgMenuAnchor(e.currentTarget)}
              aria-label={`Open organisation menu for ${orgName}`}
              aria-haspopup="true"
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                flex: 1,
                minWidth: 0,
                // Reclaim ~2 characters of width (chevron removed) before ellipsis
                mr: '-2ch',
                borderRadius: BORDER_RADIUS.pill,
                '&:hover': {
                  bgcolor: theme => theme.palette.greyscale.surface2,
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
              <Box sx={{ flex: 1, minWidth: 0 }}>
                {activeProject && (
                  <Typography
                    sx={{
                      fontSize: 18,
                      fontWeight: 700,
                      lineHeight: '25px',
                      color: theme => theme.palette.greyscale.title,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      textAlign: 'left',
                    }}
                  >
                    {activeProject.name}
                  </Typography>
                )}
                <Typography
                  sx={{
                    fontSize: 12,
                    fontWeight: 400,
                    lineHeight: '18px',
                    color: theme => theme.palette.greyscale.subtitle,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    textAlign: 'left',
                  }}
                >
                  {orgName}
                </Typography>
              </Box>
            </ButtonBase>
            {/* Collapse toggle — inline, right of brand row */}
            <Box sx={{ alignSelf: 'flex-start', flexShrink: 0 }}>
              <Tooltip title="Collapse sidebar" placement="right">
                <IconButton
                  onClick={toggle}
                  size="small"
                  aria-label="Collapse sidebar"
                  sx={{
                    p: '6px',
                    borderRadius: BORDER_RADIUS.md,
                    color: theme => theme.palette.greyscale.label,
                    '&:hover': {
                      bgcolor: theme => theme.palette.greyscale.surface2,
                    },
                  }}
                >
                  <LeftPanelCloseIcon />
                </IconButton>
              </Tooltip>
            </Box>
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
          <MenuItem
            onClick={() => {
              router.push('/organizations/settings');
              setOrgMenuAnchor(null);
            }}
            sx={{
              gap: '10px',
              px: '14px',
              py: '8px',
              '&:hover': {
                bgcolor: theme => theme.palette.greyscale.border,
              },
            }}
          >
            <SettingsOutlinedIcon
              sx={{
                fontSize: 24,
                color: theme => theme.palette.greyscale.body,
              }}
            />
            <Typography
              sx={{
                fontSize: 14,
                fontWeight: 700,
                lineHeight: '22px',
                color: theme => theme.palette.greyscale.body,
              }}
            >
              Org Settings
            </Typography>
          </MenuItem>
          <MenuItem
            onClick={() => {
              router.push('/projects');
              setOrgMenuAnchor(null);
            }}
            sx={{
              gap: '10px',
              px: '14px',
              py: '8px',
              '&:hover': {
                bgcolor: theme => theme.palette.greyscale.border,
              },
            }}
          >
            <AppsOutlinedIcon
              sx={{
                fontSize: 24,
                color: theme => theme.palette.greyscale.body,
              }}
            />
            <Typography
              sx={{
                fontSize: 14,
                fontWeight: 700,
                lineHeight: '22px',
                color: theme => theme.palette.greyscale.body,
              }}
            >
              Projects
            </Typography>
          </MenuItem>
          <Divider
            sx={{
              my: '6px',
              borderColor: theme => theme.palette.greyscale.border,
            }}
          />
          <MenuItem
            onClick={() => {
              setOrgMenuAnchor(null);
              setSwitcherOpen(true);
            }}
            sx={{
              gap: '10px',
              px: '14px',
              py: '8px',
              '&:hover': {
                bgcolor: theme => theme.palette.greyscale.border,
              },
            }}
          >
            <SwapHorizOutlinedIcon
              sx={{
                fontSize: 24,
                color: theme => theme.palette.greyscale.body,
              }}
            />
            <Typography
              sx={{
                fontSize: 14,
                fontWeight: 700,
                lineHeight: '22px',
                color: theme => theme.palette.greyscale.body,
              }}
            >
              Switch project
            </Typography>
          </MenuItem>
        </Popover>

        <ProjectSwitcherDrawer
          open={switcherOpen}
          onClose={() => setSwitcherOpen(false)}
        />

        {/* Main nav groups */}
        {mainGroups.map(group => {
          if (group.type === 'standalone') {
            return (
              <Box
                key={`standalone-${group.items.map(i => i.segment).join('-')}`}
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  ...(collapsed ? collapsedNavGroupSx : {}),
                }}
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
        {footerGroup && footerGroup.items.length > 0 && !collapsed && (
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
                onAction={action =>
                  action === 'support' && setSupportOpen(true)
                }
              />
            ))}
          </Box>
        )}

        {/* User avatar block — clickable, opens user menu */}
        <ButtonBase
          onClick={e => setMenuAnchor(e.currentTarget)}
          aria-label="Open user menu"
          aria-haspopup="true"
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: '10px',
            px: collapsed ? 0 : '10px',
            py: collapsed ? '4px' : '10px',
            width: collapsed ? COLLAPSED_NAV_ITEM_SIZE : 'auto',
            alignSelf: collapsed ? 'center' : 'stretch',
            borderRadius: BORDER_RADIUS.pill,
            overflow: 'hidden',
            '&:hover': {
              bgcolor: theme => theme.palette.greyscale.surface2,
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
                  color: theme => theme.palette.greyscale.title,
                  textDecoration: 'underline',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {user?.name ?? 'User'}
              </Typography>
            </Box>
          )}
        </ButtonBase>

        {/* ── Support drawer ── */}
        <SupportDrawer
          open={supportOpen}
          onClose={() => setSupportOpen(false)}
        />

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
          <MenuItem
            onClick={() => {
              toggleColorMode();
              setMenuAnchor(null);
            }}
            sx={{
              gap: '10px',
              px: '14px',
              py: '8px',
              '&:hover': {
                bgcolor: theme => theme.palette.greyscale.border,
              },
            }}
          >
            <DarkModeOutlinedIcon
              sx={{
                fontSize: 24,
                color: theme => theme.palette.greyscale.body,
              }}
            />
            <Typography
              sx={{
                fontSize: 14,
                fontWeight: 700,
                lineHeight: '22px',
                color: theme => theme.palette.greyscale.body,
              }}
            >
              {mode === 'dark' ? 'Light Mode' : 'Dark Mode'}
            </Typography>
          </MenuItem>

          {/* Sign Out */}
          <MenuItem
            onClick={() => handleSignOut()}
            sx={{
              gap: '10px',
              px: '14px',
              py: '8px',
              '&:hover': {
                bgcolor: theme => theme.palette.greyscale.border,
              },
            }}
          >
            <ExitToAppOutlinedIcon
              sx={{
                fontSize: 24,
                color: theme => theme.palette.greyscale.body,
              }}
            />
            <Typography
              sx={{
                fontSize: 14,
                fontWeight: 700,
                lineHeight: '22px',
                color: theme => theme.palette.greyscale.body,
              }}
            >
              Sign Out
            </Typography>
          </MenuItem>
        </Popover>
      </Box>
    </Box>
  );
}
