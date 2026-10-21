'use client';

import React, { useState } from 'react';
import {
  Avatar,
  Box,
  CircularProgress,
  InputAdornment,
  List,
  ListItemButton,
  TextField,
  Typography,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import SearchIcon from '@mui/icons-material/Search';
import { alpha, type Theme } from '@mui/material/styles';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { Project } from '@/utils/api-client/interfaces/project';
import { BORDER_RADIUS } from '@/styles/theme';
import { getProjectIcon } from '@/components/common/ProjectIcons';

const FULL_ROW_SX = (isActive: boolean) => ({
  borderRadius: BORDER_RADIUS.md,
  px: 1.5,
  py: 1.25,
  gap: 1.5,
  border: (theme: Theme) =>
    isActive
      ? `2px solid ${theme.palette.primary.main}`
      : '2px solid transparent',
  '&.Mui-selected': {
    bgcolor: (theme: Theme) =>
      theme.palette.mode === 'light' ? 'primary.50' : 'primary.900',
  },
  '&.Mui-selected:hover': {
    bgcolor: (theme: Theme) =>
      theme.palette.mode === 'light' ? 'primary.100' : 'primary.800',
  },
});

// Same geometry and hover as the popover's menu rows, so the list and the
// actions below it read as one menu. The check mark carries the active state.
const COMPACT_ROW_SX = {
  borderRadius: BORDER_RADIUS.sm,
  px: 0.75,
  py: 0.75,
  gap: 1.25,
  '&:hover, &.Mui-selected, &.Mui-selected:hover': {
    bgcolor: (theme: Theme) =>
      alpha(
        theme.palette.mode === 'light'
          ? theme.palette.common.black
          : theme.palette.common.white,
        0.06
      ),
  },
};

interface ProjectSwitcherListProps {
  onClose: () => void;
  /** Caps the list, in theme spacing units, so it scrolls under a fixed search field. */
  listMaxHeight?: number;
  /** Sidebar-popover density: nav-sized text, small icons, names only. */
  compact?: boolean;
}

/** Search field plus the member-project list; picking one makes it the active project. */
export default function ProjectSwitcherList({
  onClose,
  listMaxHeight,
  compact = false,
}: ProjectSwitcherListProps) {
  const { projects, activeProject, loading, setActiveProject } =
    useActiveProject();
  const [search, setSearch] = useState('');
  const [pendingId, setPendingId] = useState<string | null>(null);

  const filtered = projects.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase())
  );

  const handleSelect = (project: Project) => {
    // Selecting the already-active project is a no-op (no reload).
    if (String(project.id) === String(activeProject?.id)) {
      onClose();
      return;
    }
    // setActiveProject triggers a full page reload, so the spinner stays visible
    // until the navigation begins; no manual close/timeout needed.
    setPendingId(String(project.id));
    setActiveProject(project);
  };

  return (
    <>
      <TextField
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Search projects…"
        size="small"
        fullWidth
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
          },
        }}
        sx={{
          '& .MuiOutlinedInput-root': {
            borderRadius: BORDER_RADIUS.sm,
          },
          ...(compact && {
            '& .MuiInputBase-input': theme => ({
              ...theme.typography.bodyMReg,
              py: 0.75,
            }),
          }),
        }}
      />

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 2 }}>
          <CircularProgress size={24} />
        </Box>
      ) : filtered.length === 0 ? (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ textAlign: 'center', pt: 2 }}
        >
          {search ? 'No projects match your search.' : 'No projects found.'}
        </Typography>
      ) : (
        <List
          disablePadding
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 0.5,
            ...(listMaxHeight
              ? {
                  maxHeight: theme => theme.spacing(listMaxHeight),
                  overflowY: 'auto',
                }
              : {}),
          }}
        >
          {filtered.map(project => {
            const isActive = String(project.id) === String(activeProject?.id);
            const isPending = pendingId === String(project.id);
            return (
              <ListItemButton
                key={String(project.id)}
                onClick={() => handleSelect(project)}
                selected={isActive}
                sx={compact ? COMPACT_ROW_SX : FULL_ROW_SX(isActive)}
              >
                <Avatar
                  variant={compact ? 'rounded' : 'circular'}
                  sx={{
                    width: theme => theme.spacing(compact ? 2.5 : 4),
                    height: theme => theme.spacing(compact ? 2.5 : 4),
                    ...(compact && { borderRadius: BORDER_RADIUS.xs }),
                    bgcolor: 'primary.main',
                    flexShrink: 0,
                    fontSize: theme => theme.typography.body2.fontSize,
                    fontWeight: theme => theme.typography.fontWeightBold,
                    '& svg': {
                      fontSize: theme => theme.spacing(compact ? 1.5 : 2),
                    },
                  }}
                >
                  {getProjectIcon(project)}
                </Avatar>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography
                    variant={compact ? 'bodyMReg' : 'body2'}
                    sx={{
                      display: 'block',
                      fontWeight: theme =>
                        isActive
                          ? theme.typography.fontWeightBold
                          : theme.typography.fontWeightRegular,
                      color: theme => theme.palette.greyscale.title,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                    title={compact ? project.name : undefined}
                  >
                    {project.name}
                  </Typography>
                  {!compact && project.description && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{
                        display: 'block',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {project.description}
                    </Typography>
                  )}
                </Box>
                {isPending ? (
                  <CircularProgress size={16} sx={{ flexShrink: 0 }} />
                ) : isActive ? (
                  <CheckIcon
                    fontSize="small"
                    sx={{
                      color: 'primary.main',
                      flexShrink: 0,
                    }}
                  />
                ) : null}
              </ListItemButton>
            );
          })}
        </List>
      )}
    </>
  );
}
