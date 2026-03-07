'use client';

import React from 'react';
import {
  Box,
  List,
  ListItemButton,
  ListItemText,
  IconButton,
  Typography,
  Button,
  Skeleton,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import ViewSidebarOutlinedIcon from '@mui/icons-material/ViewSidebarOutlined';
import { ArchitectSession } from '@/utils/api-client/architect-client';

interface ArchitectSidebarProps {
  sessions: ArchitectSession[];
  activeSessionId: string | null;
  isLoading: boolean;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onNewSession: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
}

function formatRelativeTime(dateStr?: string): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export default function ArchitectSidebar({
  sessions,
  activeSessionId,
  isLoading,
  collapsed,
  onToggleCollapse,
  onNewSession,
  onSelectSession,
  onDeleteSession,
}: ArchitectSidebarProps) {
  if (collapsed) {
    return (
      <Box
        sx={{
          width: 48,
          borderRight: 1,
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          bgcolor: 'background.paper',
          py: 1,
          gap: 0.5,
        }}
      >
        <Tooltip title="Expand sidebar" placement="right">
          <IconButton size="small" onClick={onToggleCollapse}>
            <ViewSidebarOutlinedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="New conversation" placement="right">
          <IconButton size="small" onClick={onNewSession}>
            <AddIcon />
          </IconButton>
        </Tooltip>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: 280,
        borderRight: 1,
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.paper',
      }}
    >
      <Box
        sx={{
          p: 1,
          pl: 2,
          borderBottom: 1,
          borderColor: 'divider',
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          onClick={onNewSession}
          size="small"
          sx={{ flex: 1 }}
        >
          New conversation
        </Button>
        <Tooltip title="Collapse sidebar">
          <IconButton size="small" onClick={onToggleCollapse}>
            <ViewSidebarOutlinedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {isLoading ? (
          <Box sx={{ p: 2 }}>
            {[1, 2, 3].map(i => (
              <Skeleton
                key={i}
                variant="rectangular"
                height={48}
                sx={{ mb: 1, borderRadius: 1 }}
              />
            ))}
          </Box>
        ) : sessions.length === 0 ? (
          <Box
            sx={{
              p: 3,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              No conversations yet
            </Typography>
          </Box>
        ) : (
          <List dense disablePadding>
            {sessions.map(s => (
              <ListItemButton
                key={s.id}
                selected={s.id === activeSessionId}
                onClick={() => onSelectSession(s.id)}
                sx={{
                  px: 2,
                  py: 1,
                  '&:hover .delete-btn': { opacity: 1 },
                }}
              >
                <ListItemText
                  primary={s.title || 'Untitled'}
                  secondary={formatRelativeTime(s.updated_at)}
                  primaryTypographyProps={{
                    variant: 'body2',
                    noWrap: true,
                  }}
                  secondaryTypographyProps={{
                    variant: 'caption',
                  }}
                />
                <Tooltip title="Delete">
                  <IconButton
                    className="delete-btn"
                    size="small"
                    onClick={e => {
                      e.stopPropagation();
                      onDeleteSession(s.id);
                    }}
                    sx={{ opacity: 0, transition: 'opacity 0.2s' }}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </ListItemButton>
            ))}
          </List>
        )}
      </Box>
    </Box>
  );
}
