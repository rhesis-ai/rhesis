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
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { Project } from '@/utils/api-client/interfaces/project';
import { BORDER_RADIUS } from '@/styles/theme';
import { getProjectIcon } from '@/components/common/ProjectIcons';

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
                sx={{
                  borderRadius: BORDER_RADIUS.md,
                  px: compact ? 1 : 1.5,
                  py: compact ? 0.75 : 1.25,
                  gap: compact ? 1.25 : 1.5,
                  border: theme =>
                    isActive
                      ? `2px solid ${theme.palette.primary.main}`
                      : '2px solid transparent',
                  '&.Mui-selected': {
                    bgcolor: theme =>
                      theme.palette.mode === 'light'
                        ? 'primary.50'
                        : 'primary.900',
                  },
                  '&.Mui-selected:hover': {
                    bgcolor: theme =>
                      theme.palette.mode === 'light'
                        ? 'primary.100'
                        : 'primary.800',
                  },
                }}
              >
                <Avatar
                  sx={{
                    width: theme => theme.spacing(compact ? 3 : 4),
                    height: theme => theme.spacing(compact ? 3 : 4),
                    bgcolor: 'primary.main',
                    flexShrink: 0,
                    fontSize: theme => theme.typography.body2.fontSize,
                    fontWeight: theme => theme.typography.fontWeightBold,
                    '& svg': {
                      fontSize: theme => theme.spacing(compact ? 1.75 : 2),
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
                      // Compact wraps so long names stay readable in the narrow popover.
                      ...(compact
                        ? { overflowWrap: 'anywhere' }
                        : {
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }),
                    }}
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
