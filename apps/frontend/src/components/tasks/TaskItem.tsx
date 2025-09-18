'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Chip,
  IconButton,
  Link,
  Tooltip,
  useTheme,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  Assignment as TaskIcon,
} from '@mui/icons-material';
import { formatDistanceToNow } from 'date-fns';
import { useRouter } from 'next/navigation';
import { Task, TaskStatus, TaskPriority } from '@/types/tasks';
import { UserAvatar } from '@/components/common/UserAvatar';

interface TaskItemProps {
  task: Task;
  onEdit?: (taskId: string) => void;
  onDelete?: (taskId: string) => void;
  currentUserId: string;
  showEntityLink?: boolean;
}

export function TaskItem({ 
  task, 
  onEdit, 
  onDelete, 
  currentUserId,
  showEntityLink = false 
}: TaskItemProps) {
  const theme = useTheme();
  const router = useRouter();
  const [isHovered, setIsHovered] = useState(false);

  const isOwner = task.creator_id === currentUserId;
  const canEdit = isOwner || task.assignee_id === currentUserId;
  const canDelete = isOwner;

  const getStatusColor = (status: TaskStatus) => {
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

  const getPriorityColor = (priority: TaskPriority) => {
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

  const getEntityDisplayName = (entityType: string): string => {
    switch (entityType) {
      case 'Test':
        return 'Test';
      case 'TestSet':
        return 'Test Set';
      case 'TestRun':
        return 'Test Run';
      case 'TestResult':
        return 'Test Result';
      default:
        return entityType;
    }
  };

  const getEntityPath = (entityType: string): string => {
    switch (entityType) {
      case 'Test':
        return 'tests';
      case 'TestSet':
        return 'test-sets';
      case 'TestRun':
        return 'test-runs';
      case 'TestResult':
        return 'test-results';
      default:
        return entityType.toLowerCase();
    }
  };

  const handleTaskClick = (e: React.MouseEvent) => {
    // Prevent navigation if clicking on action buttons
    if ((e.target as HTMLElement).closest('button')) {
      return;
    }
    router.push(`/tasks/${task.id}`);
  };

  return (
    <Box
      sx={{
        p: 2,
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
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
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1, minWidth: 0 }}>
          <TaskIcon fontSize="small" color="action" />
          <Typography 
            variant="subtitle2" 
            fontWeight={600}
            sx={{ 
              flex: 1,
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}
          >
            {task.title}
          </Typography>
        </Box>

        {/* Action Buttons */}
        {(canEdit || canDelete) && (
          <Box sx={{ display: 'flex', gap: 0.5, opacity: isHovered ? 1 : 0, transition: 'opacity 0.2s' }}>
            {canEdit && (
              <Tooltip title="Edit Task">
                <IconButton
                  size="small"
                  onClick={() => onEdit?.(task.id)}
                  sx={{ 
                    color: 'text.secondary',
                    '&:hover': { color: 'primary.main' }
                  }}
                >
                  <EditIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            {canDelete && (
              <Tooltip title="Delete Task">
                <IconButton
                  size="small"
                  onClick={() => onDelete?.(task.id)}
                  sx={{ 
                    color: 'text.secondary',
                    '&:hover': { color: 'error.main' }
                  }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        )}
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
          label={task.status}
          size="small"
          color={getStatusColor(task.status)}
          variant="outlined"
        />
        <Chip
          label={task.priority}
          size="small"
          color={getPriorityColor(task.priority)}
          variant="outlined"
        />
      </Box>

      {/* Footer */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        {/* Assignee */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <UserAvatar 
            userName={task.assignee_name || task.creator_name}
            size={24}
          />
          <Typography variant="caption" color="text.secondary">
            {task.assignee_name ? `Assigned to ${task.assignee_name}` : `Created by ${task.creator_name}`}
          </Typography>
        </Box>

        {/* Timestamp */}
        <Typography variant="caption" color="text.secondary">
          {formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}
        </Typography>
      </Box>

      {/* Entity Link */}
      {showEntityLink && (
        <Box sx={{ mt: 1, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
          <Typography variant="caption" color="text.secondary">
            Related to: {getEntityDisplayName(task.entity_type)}
          </Typography>
        </Box>
      )}

      {/* Comment Link */}
      {task.comment_id && (
        <Box sx={{ mt: 1, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
          <Link 
            href={`/${getEntityPath(task.entity_type)}/${task.entity_id}#comment-${task.comment_id}`}
            sx={{ 
              textDecoration: 'none',
              '&:hover': { textDecoration: 'underline' }
            }}
          >
            <Typography variant="caption" color="primary">
              Created from comment → View Comment
            </Typography>
          </Link>
        </Box>
      )}
    </Box>
  );
}
