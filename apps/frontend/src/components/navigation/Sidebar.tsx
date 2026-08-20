'use client';

import React, { useState, useContext } from 'react';
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
import Badge from '@mui/material/Badge';
import MuiLink from '@mui/material/Link';
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined';
import NotificationsOutlinedIcon from '@mui/icons-material/NotificationsOutlined';
import ExitToAppOutlinedIcon from '@mui/icons-material/ExitToAppOutlined';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import AppsOutlinedIcon from '@mui/icons-material/AppsOutlined';
import DataUsageOutlinedIcon from '@mui/icons-material/DataUsageOutlined';
import SwapHorizOutlinedIcon from '@mui/icons-material/SwapHorizOutlined';
import Divider from '@mui/material/Divider';
import { useNavigationItems } from '@/contexts/NavigationItemsContext';
import { useSidebarCollapse } from '@/components/layout/AppShell';
import BrandMark from '@/components/common/BrandMark';
import { UserAvatar } from '@/components/common/UserAvatar';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useUsage } from '@/contexts/UsageContext';
import {
  QUOTA_RESOURCE_LABELS,
  QUOTA_RESOURCE_ORDER,
  UPGRADE_URL,
} from '@/constants/quota';
import {
  flaggedResources,
  isCommunityEdition,
  quotaCopy,
  usageMenuRows,
  zoneColor,
  type UsageRow,
} from '@/utils/quota';
import { PlanChip } from '@/components/common/QuotaChips';
import { ColorModeContext } from '@/components/providers/ThemeProvider';
import { handleSignOut } from '@/actions/auth';
import {
  SIDEBAR_WIDTH,
  SIDEBAR_COLLAPSED_WIDTH,
} from '@/components/layout/sidebar-constants';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { alpha, type Theme } from '@mui/material/styles';
import {
  type ExtendedUser,
  type StandaloneGroup,
  type SectionGroup,
  type FooterLinksGroup,
  groupNavItems,
  collapsedNavGroupSx,
  COLLAPSED_NAV_ITEM_SIZE,
  COUNT_BADGE_SX,
} from './sidebar-utils';
import { NavItem } from './NavItem';
import { NavLinkItem } from './NavLinkItem';
import { NavSection } from './NavSection';
import ProjectSwitcherDrawer from './ProjectSwitcherDrawer';
import SupportDrawer from './SupportDrawer';
import NotificationsDrawer from './NotificationsDrawer';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { useNotifications } from '@/contexts/NotificationsContext';

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

// Collapse-toggle geometry. TOGGLE_LIFT_PX pulls the expanded toggle out of the
// brand row by its own full height so it clears the project name — it is derived
// from the two values below rather than hard-coded, and both are applied to the
// icon and the button, so the alignment holds if either changes.
const TOGGLE_ICON_PX = 24;
const TOGGLE_BUTTON_PADDING_PX = 6;
const TOGGLE_LIFT_PX = TOGGLE_ICON_PX + TOGGLE_BUTTON_PADDING_PX;
// Nudge toward the sidebar edge, into its 26px side padding.
const TOGGLE_NUDGE_RIGHT_PX = 8;

// Rows the org-menu usage block always shows, padding flagged resources with
// the next ones in canonical order so it never reads as near-empty for a
// healthy org. A floor, never a cap: every flagged resource gets a row, so
// the row count always agrees with the badge.
const MIN_USAGE_ROWS = 3;

// Shared row style for the org and user menu popovers (Figma 860:40824).
// Every row in both menus uses this; a row with a trailing badge overrides
// `justifyContent` to 'space-between'.
const MENU_ROW_SX = {
  gap: '10px',
  px: '14px',
  py: '8px',
  '&:hover': {
    bgcolor: (theme: Theme) => theme.palette.greyscale.border,
  },
} as const;

// Icon + label pair inside a menu row.
const MENU_ICON_SX = {
  fontSize: 24,
  color: (theme: Theme) => theme.palette.greyscale.body,
} as const;

const MENU_LABEL_SX = {
  fontSize: 14,
  fontWeight: 700,
  lineHeight: '22px',
  color: (theme: Theme) => theme.palette.greyscale.body,
} as const;

function LeftPanelCloseIcon() {
  return (
    <SvgIcon viewBox="0 0 24 24" sx={{ fontSize: TOGGLE_ICON_PX }}>
      <path d={LEFT_PANEL_PATH} fill="currentColor" />
    </SvgIcon>
  );
}

function LeftPanelOpenIcon() {
  // Mirror horizontally: arrow now points right, indicating "open left panel"
  return (
    <SvgIcon
      viewBox="0 0 24 24"
      sx={{ fontSize: TOGGLE_ICON_PX, transform: 'scaleX(-1)' }}
    >
      <path d={LEFT_PANEL_PATH} fill="currentColor" />
    </SvgIcon>
  );
}

/** `"Aug 2026"` -- the org-menu usage block's header month. Stays in
 * UTC: `period_end` is a date-only string computed in UTC by the backend. */
function formatMonthLabel(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString('en-US', {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/** One row of the org-menu usage block: a resource's label plus its
 * value, coloured by zone -- flow resources show a percent, stock
 * resources show a count, matching `QuotaBanner`'s split for the same
 * reason (a flow resource's raw count means nothing without the period
 * it accrued over; a stock resource's raw count is the whole story). */
function UsageMenuRow({ resource, item, zone }: UsageRow) {
  const label = QUOTA_RESOURCE_LABELS[resource];
  const value =
    item.kind === 'stock' || item.limit === null || item.limit === 0
      ? `${item.used.toLocaleString()} of ${(item.limit ?? 0).toLocaleString()}`
      : `${Math.round((item.used / item.limit) * 100)}%`;

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        px: '14px',
        py: '2px',
      }}
    >
      <Typography
        variant="caption"
        sx={{ color: theme => theme.palette.greyscale.label }}
      >
        {label}
      </Typography>
      <Typography
        variant="caption"
        sx={{
          fontWeight: 600,
          fontVariantNumeric: 'tabular-nums',
          color: theme =>
            zone === 'healthy'
              ? theme.palette.greyscale.label
              : theme.palette[zoneColor(zone)].main,
        }}
      >
        {value}
      </Typography>
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

  // Project switcher drawer
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const { activeProject } = useActiveProject();

  // Support drawer
  const [supportOpen, setSupportOpen] = useState(false);

  // Notifications drawer
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const { unreadBySection } = useNotifications();
  const totalUnread = Object.values(unreadBySection).reduce(
    (sum, count) => sum + (count ?? 0),
    0
  );

  // Quota awareness: `usage:read` is granted to every org member (see
  // `auth/rbac.py`'s comment on `Usage.READ`), so the badge and org-menu
  // block below show to everyone -- `UsageContext`'s own fail-closed
  // contract (an empty `resources` while loading or on error) is what
  // keeps this quiet until there is real data, not a permission check.
  // "Can upgrade" is a narrower, separate question: Organization.UPDATE
  // (the same owner/admin gate as Org Settings), not Usage.READ.
  const { resources: usageResources, edition } = useUsage();
  const flaggedUsage = flaggedResources(usageResources);
  const flaggedCount = flaggedUsage.length;
  const canManageOrg = useCan(Capability.Organization.UPDATE);
  const canUpgrade =
    canManageOrg && edition !== null && isCommunityEdition(edition);

  // The badge answers "how many"; the sentence (only rendered as a tooltip
  // here, in full in the org-menu block below) answers "how bad" -- no
  // severity colour on the badge itself.
  let usageTooltip: string | null = null;
  const worst = flaggedCount === 1 ? flaggedUsage[0] : null;
  if (worst) {
    usageTooltip = quotaCopy({
      resource: worst.resource,
      kind: worst.item.kind,
      used: worst.item.used,
      limit: worst.item.limit ?? 0,
      zone: worst.zone,
      periodEnd: worst.item.period_end,
      canUpgrade,
    }).sentence;
  } else if (flaggedCount > 1) {
    usageTooltip = `Your organization has ${flaggedCount} resources at or near their limit.`;
  }

  const usageRows = usageMenuRows(
    usageResources,
    QUOTA_RESOURCE_ORDER,
    MIN_USAGE_ROWS
  );
  // Specifically a flow resource, for the same reason UsageOverviewTab picks
  // one deliberately: stock items always carry the *current* period, so
  // taking whichever resource happens to come first would silently mislabel
  // the block the moment the two periods differ.
  const usagePeriodSource = Object.values(usageResources).find(
    resourceItem => resourceItem.kind === 'flow'
  );
  const usagePeriodLabel = usagePeriodSource
    ? formatMonthLabel(usagePeriodSource.period_end)
    : null;

  // Reordered around the usage block below, not fixed: with a block to
  // show, "Switch project" and the divider move ahead of it so the everyday
  // navigation items stay together at the top instead of splitting across a
  // wall of usage rows. With nothing to show, "Org usage" is just another
  // nav row and stays where it was.
  const orgUsageSection = (
    <>
      {/* Named "Org usage", not "Usage": the menu already reads "Org
          Settings" two rows up, and quota is organization state, never
          personal -- see IMPLEMENTATION_PROMPT.md's "the rule". Visible to
          every member, not just admins: `usage:read` is granted org-wide
          (see the note where `canManageOrg` is computed above). Only the
          "Upgrade plan" row below is narrower. */}
      <MenuItem
        onClick={() => {
          router.push('/organizations/usage');
          setOrgMenuAnchor(null);
        }}
        sx={{ ...MENU_ROW_SX, justifyContent: 'space-between' }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <DataUsageOutlinedIcon
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
            Org usage
          </Typography>
        </Box>
        {flaggedCount > 0 && (
          <Box sx={{ ...COUNT_BADGE_SX, flexShrink: 0 }}>
            {flaggedCount > 99 ? '99+' : flaggedCount}
          </Box>
        )}
      </MenuItem>
      {/* Gated on rows, not on `usageResources` being non-empty: a
          deployment with USAGE_QUOTAS_ENABLED off reports every resource
          with a null limit, which yields no rows, and a period-and-plan
          header standing alone over nothing is worse than no block. */}
      {usageRows.length > 0 && (
        <Box sx={{ pb: '8px' }}>
          {/* The header and rows are their own click target -- same
              destination as the "Org usage" row above, so a reader doesn't
              have to aim for that one specific row when the whole block is
              about the same page. "Upgrade plan" stays a sibling outside
              this button, not nested in it: nested interactive elements
              would fire both on a single click. */}
          <ButtonBase
            onClick={() => {
              router.push('/organizations/usage');
              setOrgMenuAnchor(null);
            }}
            sx={{
              display: 'block',
              width: '100%',
              textAlign: 'left',
              borderRadius: BORDER_RADIUS.sm,
            }}
          >
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                px: '14px',
                py: '4px',
              }}
            >
              <Typography
                variant="caption"
                sx={{ color: theme => theme.palette.greyscale.subtitle }}
              >
                {usagePeriodLabel ?? 'Current usage'}
              </Typography>
              {edition && <PlanChip edition={edition} />}
            </Box>
            {usageRows.map(row => (
              <UsageMenuRow key={row.resource} {...row} />
            ))}
          </ButtonBase>
          {canUpgrade && (
            <Box sx={{ px: '14px', pt: '6px' }}>
              <MuiLink
                href={UPGRADE_URL}
                target="_blank"
                rel="noopener noreferrer"
                variant="caption"
                sx={{ fontWeight: 700 }}
              >
                Upgrade plan →
              </MuiLink>
            </Box>
          )}
        </Box>
      )}
    </>
  );

  // A soft alpha overlay on the popover's own surface, not
  // `greyscale.border`: that token is tuned for the app's regular
  // greyscale.surface1/2 backgrounds, and against this popover's own
  // near-black (dark mode) / near-white (light mode) paper background, set
  // just below, it sat close enough in luminance to read as no divider
  // at all.
  const orgMenuDivider = (
    <Divider
      sx={{
        my: '6px',
        borderColor: theme =>
          alpha(
            theme.palette.mode === 'light'
              ? theme.palette.common.black
              : theme.palette.common.white,
            0.14
          ),
      }}
    />
  );

  const switchProjectItem = (
    <MenuItem
      onClick={() => {
        setOrgMenuAnchor(null);
        setSwitcherOpen(true);
      }}
      sx={MENU_ROW_SX}
    >
      <SwapHorizOutlinedIcon sx={MENU_ICON_SX} />
      <Typography sx={MENU_LABEL_SX}>Switch project</Typography>
    </MenuItem>
  );

  const orgName = branding?.title ?? branding?.productName ?? 'Rhesis AI';
  const groups = groupNavItems(navigation);

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
        bgcolor: theme => theme.palette.greyscale.surface1,
        px: collapsed ? '12px' : '26px',
        // Top padding lives on the scrolling section below, not here, so the
        // collapse toggle can be pulled up into it without being clipped.
        pt: 0,
        pb: '30px',
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
          gap: 'var(--nav-group-gap)',
          flex: 1,
          // Must stay >= the toggle's lift above, or the toggle is clipped.
          pt: '30px',
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
                  p: `${TOGGLE_BUTTON_PADDING_PX}px`,
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
                usageTooltip
                  ? `${activeProject ? `${orgName} · ${activeProject.name}` : orgName} — ${usageTooltip}`
                  : activeProject
                    ? `${orgName} · ${activeProject.name}`
                    : orgName
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
                {flaggedCount > 0 ? (
                  <Badge badgeContent={flaggedCount} color="primary" max={99}>
                    <BrandMark
                      src={branding?.iconUrl}
                      size={40}
                      alt={`${orgName} logo`}
                      priority
                    />
                  </Badge>
                ) : (
                  <BrandMark
                    src={branding?.iconUrl}
                    size={40}
                    alt={`${orgName} logo`}
                    priority
                  />
                )}
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
                // The toggle now sits a full icon height above this row, so the
                // name can run under it. Reclaim most of its footprint but stop
                // short of the sidebar's right padding — the full 44px pushed
                // the ellipsis past the edge, where overflowX hid it.
                mr: '-28px',
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
                <BrandMark
                  src={branding?.iconUrl}
                  size={40}
                  alt={`${orgName} logo`}
                  priority
                />
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                {activeProject && (
                  <Typography
                    sx={{
                      fontSize: 14,
                      fontWeight: 700,
                      lineHeight: '20px',
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
              {flaggedCount > 0 && (
                <Tooltip title={usageTooltip ?? ''} placement="right">
                  <Box
                    sx={{
                      ...COUNT_BADGE_SX,
                      flexShrink: 0,
                      // Cancels the ButtonBase's own -28px so the badge's
                      // right edge lands at the same inset as every nav-row
                      // badge, instead of 28px further into the sidebar's
                      // padding along with the rest of this button's content.
                      mr: '28px',
                    }}
                  >
                    {flaggedCount > 99 ? '99+' : flaggedCount}
                  </Box>
                </Tooltip>
              )}
            </ButtonBase>
            {/* Collapse toggle — inline, right of brand row. Lifted a full icon
                height clear of the project name, into the scrolling section's
                top padding. */}
            <Box
              sx={{
                alignSelf: 'flex-start',
                flexShrink: 0,
                mt: `-${TOGGLE_LIFT_PX}px`,
                mr: `-${TOGGLE_NUDGE_RIGHT_PX}px`,
              }}
            >
              <Tooltip title="Collapse sidebar" placement="right">
                <IconButton
                  onClick={toggle}
                  size="small"
                  aria-label="Collapse sidebar"
                  sx={{
                    p: `${TOGGLE_BUTTON_PADDING_PX}px`,
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
                // 252px, not the 188px the user-menu popover uses: this one carries the
                // usage block's period label + plan chip on one row, which needs
                // breathing room between them.
                minWidth: 252,
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
            sx={MENU_ROW_SX}
          >
            <SettingsOutlinedIcon sx={MENU_ICON_SX} />
            <Typography sx={MENU_LABEL_SX}>Org Settings</Typography>
          </MenuItem>
          <MenuItem
            onClick={() => {
              router.push('/projects');
              setOrgMenuAnchor(null);
            }}
            sx={MENU_ROW_SX}
          >
            <AppsOutlinedIcon sx={MENU_ICON_SX} />
            <Typography sx={MENU_LABEL_SX}>Projects</Typography>
          </MenuItem>
          {usageRows.length > 0 ? (
            <>
              {switchProjectItem}
              {orgMenuDivider}
              {orgUsageSection}
            </>
          ) : (
            <>
              {orgUsageSection}
              {orgMenuDivider}
              {switchProjectItem}
            </>
          )}
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
                  gap: 'var(--nav-item-gap)',
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

        {/* ── Notifications drawer ── */}
        <NotificationsDrawer
          open={notificationsOpen}
          onClose={() => setNotificationsOpen(false)}
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
          {/* Notifications */}
          <MenuItem
            onClick={() => {
              setMenuAnchor(null);
              setNotificationsOpen(true);
            }}
            sx={{ ...MENU_ROW_SX, justifyContent: 'space-between' }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <NotificationsOutlinedIcon sx={MENU_ICON_SX} />
              <Typography sx={MENU_LABEL_SX}>Notifications</Typography>
            </Box>
            {totalUnread > 0 && (
              <Box sx={{ ...COUNT_BADGE_SX, flexShrink: 0 }}>
                {totalUnread > 99 ? '99+' : totalUnread}
              </Box>
            )}
          </MenuItem>

          {/* Dark Mode */}
          <MenuItem
            onClick={() => {
              toggleColorMode();
              setMenuAnchor(null);
            }}
            sx={MENU_ROW_SX}
          >
            <DarkModeOutlinedIcon sx={MENU_ICON_SX} />
            <Typography sx={MENU_LABEL_SX}>
              {mode === 'dark' ? 'Light Mode' : 'Dark Mode'}
            </Typography>
          </MenuItem>

          {/* Sign Out */}
          <MenuItem onClick={() => handleSignOut()} sx={MENU_ROW_SX}>
            <ExitToAppOutlinedIcon sx={MENU_ICON_SX} />
            <Typography sx={MENU_LABEL_SX}>Sign Out</Typography>
          </MenuItem>
        </Popover>
      </Box>
    </Box>
  );
}
