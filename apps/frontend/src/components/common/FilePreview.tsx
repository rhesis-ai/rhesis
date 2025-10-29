'use client';

import React, { useState } from 'react';
import {
  Paper,
  Box,
  Typography,
  IconButton,
  Tooltip,
  Collapse,
} from '@mui/material';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { useNotifications } from '@/components/common/NotificationContext';

interface FilePreviewProps {
  /**
   * Title/name of the source
   */
  title: string;
  /**
   * Content of the file to display
   */
  content: string;
  /**
   * Optional description for the file
   */
  description?: string;
  /**
   * Whether to show copy button (default: true)
   */
  showCopyButton?: boolean;
  /**
   * Initially expanded state (default: false)
   */
  defaultExpanded?: boolean;
}

/**
 * FilePreview Component
 * A reusable, collapsible file preview component using MUI Paper
 * Displays file content with expand/collapse functionality and optional copy button
 */
export default function FilePreview({
  title,
  content,
  description,
  showCopyButton = true,
  defaultExpanded = false,
}: FilePreviewProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const notifications = useNotifications();

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      notifications.show('Content copied to clipboard', {
        severity: 'success',
      });
    } catch (err) {
      notifications.show('Failed to copy content', { severity: 'error' });
    }
  };

  return (
    <Paper
      variant="outlined"
      sx={{
        overflow: 'hidden',
        backgroundColor: 'background.paper',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 2,
          bgcolor: 'action.hover',
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
          <InsertDriveFileOutlined
            sx={{
              fontSize: 20,
              color: 'text.secondary',
            }}
          />
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 500,
                color: 'text.primary',
                wordBreak: 'break-word',
              }}
            >
              {title}
            </Typography>
            {description && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', mt: 0.5 }}
              >
                {description}
              </Typography>
            )}
          </Box>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {showCopyButton && (
            <Tooltip title="Copy Content">
              <IconButton size="small" onClick={handleCopy}>
                <ContentCopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title={isExpanded ? 'Collapse' : 'Expand'}>
            <IconButton size="small" onClick={() => setIsExpanded(!isExpanded)}>
              {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Content */}
      <Collapse in={isExpanded}>
        <Box
          sx={{
            p: 2,
            bgcolor: 'background.default',
            maxHeight: 400,
            overflow: 'auto',
            borderTop: 1,
            borderColor: 'divider',
          }}
        >
          <Typography
            component="pre"
            sx={{
              margin: 0,
              fontFamily: 'monospace',
              fontSize: theme => theme.typography.body2.fontSize,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              color: 'text.primary',
            }}
          >
            {content || 'No content available'}
          </Typography>
        </Box>
      </Collapse>
    </Paper>
  );
}
