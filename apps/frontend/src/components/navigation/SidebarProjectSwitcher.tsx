'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import ButtonBase from '@mui/material/ButtonBase';
import Divider from '@mui/material/Divider';
import MenuItem from '@mui/material/MenuItem';
import Popover from '@mui/material/Popover';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import AddOutlinedIcon from '@mui/icons-material/AddOutlined';
import AppsOutlinedIcon from '@mui/icons-material/AppsOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import { alpha, type Theme } from '@mui/material/styles';
import { Can } from '@/components/common/Can';
import { getProjectIcon } from '@/components/common/ProjectIcons';
import { Capability } from '@/constants/capabilities';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { BORDER_RADIUS } from '@/styles/theme';
import ProjectSwitcherList from './ProjectSwitcherList';
import {
  COLLAPSED_NAV_ITEM_SIZE,
  MENU_DIVIDER_SX,
  MENU_ICON_SX,
  MENU_ROW_SX,
  POPOVER_PAPER_SX,
} from './sidebar-utils';

// In theme spacing units: room for ~7 projects before the list scrolls under
// the search field.
const LIST_MAX_HEIGHT = 40;
const POPOVER_WIDTH = 32.5;

const NO_PROJECT_LABEL = 'Select a project';

interface SidebarProjectSwitcherProps {
  collapsed: boolean;
}

/**
 * The active project, shown as a row above the nav so it reads as the
 * scope of every item below it. Opens a menu with the project's settings, the
 * project list, and the org-level project overview and create page.
 */
export function SidebarProjectSwitcher({
  collapsed,
}: SidebarProjectSwitcherProps) {
  const router = useRouter();
  const { activeProject } = useActiveProject();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const close = () => setAnchor(null);

  const triggerProps = {
    onClick: (e: React.MouseEvent<HTMLElement>) => setAnchor(e.currentTarget),
    'aria-label': activeProject
      ? `Switch project, current: ${activeProject.name}`
      : NO_PROJECT_LABEL,
    'aria-haspopup': true,
    'aria-expanded': Boolean(anchor),
  };

  const goTo = (path: string) => {
    close();
    router.push(path);
  };

  const tile = (
    <Avatar
      variant="rounded"
      sx={{
        width: theme => theme.spacing(3),
        height: theme => theme.spacing(3),
        flexShrink: 0,
        borderRadius: BORDER_RADIUS.xs,
        bgcolor: 'primary.main',
        '& svg': { fontSize: theme => theme.spacing(2) },
      }}
    >
      {activeProject ? getProjectIcon(activeProject) : null}
    </Avatar>
  );

  // The same white card as the footer, so the sidebar has one card style.
  const cardSx = {
    bgcolor: (theme: Theme) =>
      theme.palette.mode === 'light'
        ? theme.palette.background.paper
        : theme.palette.background.light3,
    boxShadow: (theme: Theme) =>
      `0px 1px 2px ${alpha(theme.palette.common.black, 0.06)}`,
    // A border, not an outline: the sidebar's scroll container clips anything
    // drawn outside the box.
    border: '1px solid',
    borderColor: (theme: Theme) =>
      anchor ? theme.palette.greyscale.border : 'transparent',
    '&:hover': {
      borderColor: (theme: Theme) => theme.palette.greyscale.border,
    },
  };

  const trigger = collapsed ? (
    <Tooltip
      title={
        activeProject ? `Project: ${activeProject.name}` : NO_PROJECT_LABEL
      }
      placement="right"
    >
      <ButtonBase
        {...triggerProps}
        sx={{
          width: COLLAPSED_NAV_ITEM_SIZE,
          height: COLLAPSED_NAV_ITEM_SIZE,
          alignSelf: 'center',
          flexShrink: 0,
          borderRadius: BORDER_RADIUS.md,
          ...cardSx,
        }}
      >
        {tile}
      </ButtonBase>
    </Tooltip>
  ) : (
    <Tooltip
      title={activeProject?.name ?? ''}
      placement="right"
      enterDelay={500}
      disableHoverListener={Boolean(anchor)}
    >
      <ButtonBase
        {...triggerProps}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          width: '100%',
          flexShrink: 0,
          px: '14px',
          py: 1.25,
          textAlign: 'left',
          borderRadius: BORDER_RADIUS.md,
          ...cardSx,
        }}
      >
        <Typography
          variant="bodyMBold"
          component="div"
          sx={{
            flex: 1,
            minWidth: 0,
            color: theme =>
              activeProject
                ? theme.palette.greyscale.title
                : theme.palette.greyscale.subtitle,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {activeProject?.name ?? NO_PROJECT_LABEL}
        </Typography>
        <ExpandMoreIcon
          sx={{
            flexShrink: 0,
            fontSize: theme => theme.spacing(2),
            color: theme => theme.palette.greyscale.subtitle,
          }}
        />
      </ButtonBase>
    </Tooltip>
  );

  return (
    <>
      {trigger}
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={close}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{
          paper: {
            sx: {
              ...POPOVER_PAPER_SX,
              mt: 0.5,
              py: 1,
              width: theme => theme.spacing(POPOVER_WIDTH),
            },
          },
        }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 1,
            px: 1,
          }}
        >
          <ProjectSwitcherList
            onClose={close}
            listMaxHeight={LIST_MAX_HEIGHT}
            compact
          />
        </Box>
        <Divider sx={MENU_DIVIDER_SX} />
        {/* Switching is what the menu is for, so the actions sit below it. */}
        {activeProject && (
          <MenuItem
            onClick={() => goTo(`/projects/${activeProject.id}`)}
            sx={MENU_ROW_SX}
          >
            <SettingsOutlinedIcon fontSize="small" sx={MENU_ICON_SX} />
            <Typography variant="bodyMReg">Project Settings</Typography>
          </MenuItem>
        )}
        {/* The full overview is org-level, like the org menu's "Projects". */}
        <MenuItem onClick={() => goTo('/projects')} sx={MENU_ROW_SX}>
          <AppsOutlinedIcon fontSize="small" sx={MENU_ICON_SX} />
          <Typography variant="bodyMReg">All Projects</Typography>
        </MenuItem>
        <Can capability={Capability.Project.CREATE}>
          <MenuItem
            onClick={() => goTo('/projects/create-new')}
            sx={MENU_ROW_SX}
          >
            <AddOutlinedIcon fontSize="small" sx={MENU_ICON_SX} />
            <Typography variant="bodyMReg">New Project</Typography>
          </MenuItem>
        </Can>
      </Popover>
    </>
  );
}

export default SidebarProjectSwitcher;
