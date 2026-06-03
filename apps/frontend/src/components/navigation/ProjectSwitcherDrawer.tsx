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
import { FilterDrawerShell } from '@/components/common/FilterDrawer';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { Project } from '@/utils/api-client/interfaces/project';
import { BORDER_RADIUS } from '@/styles/theme';
import { getProjectIcon } from '@/components/common/ProjectIcons';

interface ProjectSwitcherDrawerProps {
  open: boolean;
  onClose: () => void;
}

export default function ProjectSwitcherDrawer({
  open,
  onClose,
}: ProjectSwitcherDrawerProps) {
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
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={onClose}
      resetLabel="Cancel"
      title="Switch project"
    >
      {/* Search */}
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
        }}
      />

      {/* Project list */}
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
        <List disablePadding sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
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
                  px: 1.5,
                  py: 1.25,
                  gap: 1.5,
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
                    width: theme => theme.spacing(4),
                    height: theme => theme.spacing(4),
                    bgcolor: 'primary.main',
                    flexShrink: 0,
                    fontSize: theme => theme.typography.body2.fontSize,
                    fontWeight: theme => theme.typography.fontWeightBold,
                    '& svg': { fontSize: theme => theme.spacing(2) },
                  }}
                >
                  {getProjectIcon(project)}
                </Avatar>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography
                    variant="body2"
                    sx={{
                      fontWeight: theme =>
                        isActive
                          ? theme.typography.fontWeightBold
                          : theme.typography.fontWeightRegular,
                      color: theme => theme.palette.greyscale.title,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {project.name}
                  </Typography>
                  {project.description && (
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
    </FilterDrawerShell>
  );
}
