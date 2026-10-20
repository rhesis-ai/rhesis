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
import type { Theme } from '@mui/material/styles';
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
 * The active project, shown as its own box above the nav so it reads as the
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
          border: (theme: Theme) =>
            `1px solid ${theme.palette.greyscale.border}`,
          bgcolor: 'background.paper',
          '&:hover': { borderColor: 'primary.main' },
        }}
      >
        <Avatar
          sx={{
            width: theme => theme.spacing(3),
            height: theme => theme.spacing(3),
            bgcolor: 'primary.main',
            '& svg': { fontSize: theme => theme.spacing(1.75) },
          }}
        >
          {activeProject ? getProjectIcon(activeProject) : null}
        </Avatar>
      </ButtonBase>
    </Tooltip>
  ) : (
    <ButtonBase
      {...triggerProps}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        width: '100%',
        flexShrink: 0,
        px: 1.25,
        py: 0.75,
        textAlign: 'left',
        borderRadius: BORDER_RADIUS.sm,
        border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
        bgcolor: 'background.paper',
        transition: theme =>
          theme.transitions.create('border-color', {
            duration: theme.transitions.duration.shortest,
          }),
        '&:hover': { borderColor: 'primary.main' },
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {/* Same type as the nav section headers (DEFINE, GENERATE…). */}
        <Typography variant="overline" component="div">
          Project
        </Typography>
        <Typography
          variant="bodyMBold"
          component="div"
          sx={{
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
      </Box>
      <ExpandMoreIcon
        sx={{
          flexShrink: 0,
          color: theme => theme.palette.greyscale.subtitle,
        }}
      />
    </ButtonBase>
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
              width: theme => theme.spacing(POPOVER_WIDTH),
            },
          },
        }}
      >
        {activeProject && (
          <>
            <MenuItem
              onClick={() => goTo(`/projects/${activeProject.id}`)}
              sx={MENU_ROW_SX}
            >
              <SettingsOutlinedIcon fontSize="small" sx={MENU_ICON_SX} />
              <Typography variant="bodyMReg">Project Settings</Typography>
            </MenuItem>
            <Divider sx={MENU_DIVIDER_SX} />
          </>
        )}
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 1,
            px: 1.5,
            py: 0.5,
          }}
        >
          <ProjectSwitcherList
            onClose={close}
            listMaxHeight={LIST_MAX_HEIGHT}
            compact
          />
        </Box>
        <Divider sx={MENU_DIVIDER_SX} />
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
