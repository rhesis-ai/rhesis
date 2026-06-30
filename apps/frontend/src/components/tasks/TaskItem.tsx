'use client';

import React, { useState } from 'react';
import { Box, Typography, Chip, Tooltip, useTheme } from '@mui/material';
import { EditIcon, DeleteIcon, AssignmentIcon } from '@/components/icons';
import { useRouter } from 'next/navigation';
import type { Task } from '@/types/tasks';
import { EntityType } from '@/types/entity-type';
import { getEntityDisplayName } from '@/utils/entity-helpers';
import { UserAvatar } from '@/components/common/UserAvatar';
import { EntityAction } from '@/components/common/entity-actions';
import { EntityActionBar } from '@/components/common/EntityActionBar';
import { Capability } from '@/constants/capabilities';

interface TaskItemProps {
  task: Task;
  onEdit?: (taskId: string) => void;
  onDelete?: (taskId: string) => void;
  showEntityLink?: boolean;
}

const TASK_ACTION_DESCRIPTORS: Omit<EntityAction<Task>, 'onSelect'>[] = [
  {
    id: 'edit',
    label: 'Edit Task',
    icon: EditIcon,
    capability: Capability.Task.UPDATE,
  },
  {
    id: 'delete',
    label: 'Delete Task',
    icon: DeleteIcon,
    capability: Capability.Task.DELETE,
  },
];

export function TaskItem({
  task,
  onEdit,
  onDelete,
  showEntityLink = false,
}: TaskItemProps) {
  const theme = useTheme();
  const router = useRouter();
  const [isHovered, setIsHovered] = useState(false);

  const actions: EntityAction<Task>[] = [
    { ...TASK_ACTION_DESCRIPTORS[0], onSelect: (t: Task) => onEdit?.(t.id) },
    { ...TASK_ACTION_DESCRIPTORS[1], onSelect: (t: Task) => onDelete?.(t.id) },
  ];

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'Open':
        return 'default';
      case 'In Progress':
        return 'primary';
      case 'Completed':
        return 'success';
      case 'Cancelled':
        return 'error';
      default:
        return 'default';
    }
  };

  const getPriorityColor = (priority?: string) => {
    switch (priority) {
      case 'Low':
        return 'default';
      case 'Medium':
        return 'warning';
      case 'High':
        return 'error';
      default:
        return 'default';
    }
  };

  const handleTaskClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button')) {
      return;
    }

    try {
      router.push(`/tasks/${task.id}`);
    } catch (_error) {
      // Could show notification or handle gracefully
    }
  };

  return (
    <Box
      sx={{
        p: 2,
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: theme.shape.borderRadius,
        bgcolor: 'background.paper',
        transition: 'all 0.2s ease-in-out',
        cursor: 'pointer',
        '&:hover': {
          borderColor: 'primary.main',
          boxShadow: 1,
        },
        mb: 1,
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={handleTaskClick}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          mb: 1,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            flex: 1,
            minWidth: 0,
          }}
        >
          <Tooltip title="Task">
            <AssignmentIcon fontSize="small" color="action" />
          </Tooltip>
          <Typography
            variant="subtitle2"
            fontWeight={600}
            sx={{
              flex: 1,
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {task.title}
          </Typography>
        </Box>

        {/* Server-driven action bar — visibility derived from permitted_actions */}
        <Box
          sx={{
            opacity: isHovered ? 1 : 0,
            transition: 'opacity 0.2s',
          }}
        >
          <EntityActionBar subject={task} actions={actions} iconSize={18} />
        </Box>
      </Box>

      {/* Description */}
      {task.description && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mb: 2, lineHeight: 1.4 }}
        >
          {task.description}
        </Typography>
      )}

      {/* Status and Priority */}
      <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        <Chip
          label={task.status?.name || 'Unknown'}
          size="small"
          color={getStatusColor(task.status?.name)}
          variant="outlined"
        />
        <Chip
          label={task.priority?.type_value || 'Unknown'}
          size="small"
          color={getPriorityColor(task.priority?.type_value)}
          variant="outlined"
        />
      </Box>

      {/* Footer */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        {/* Assignee */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <UserAvatar
            userName={task.assignee?.name || task.user?.name || 'Unknown'}
            size={24}
          />
          <Typography variant="caption" color="text.secondary">
            {task.assignee?.name
              ? `Assigned to ${task.assignee.name}`
              : `Created by ${task.user?.name}`}
          </Typography>
        </Box>

        {/* Timestamp */}
        <Typography variant="caption" color="text.secondary">
          {task.nano_id || task.id?.slice(0, 8) || 'N/A'}
        </Typography>
      </Box>

      {/* Entity Link */}
      {showEntityLink && (
        <Box
          sx={{ mt: 1, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}
        >
          <Typography variant="caption" color="text.secondary">
            Related to:{' '}
            {getEntityDisplayName(
              (task.entity_type as EntityType) || EntityType.TASK
            )}
          </Typography>
        </Box>
      )}
    </Box>
  );
}
