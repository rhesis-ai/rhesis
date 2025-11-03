'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  IconButton,
  Tooltip,
  Collapse,
  useTheme,
  TextField,
} from '@mui/material';
import { Source } from '@/utils/api-client/interfaces/source';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import DownloadIcon from '@mui/icons-material/Download';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import EditIcon from '@mui/icons-material/Edit';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import styles from '@/styles/Knowledge.module.css';
import {
  FILE_SIZE_CONSTANTS,
  TEXT_CONSTANTS,
  formatFileSize,
  formatDate,
  getFileExtension,
  truncateFilename,
} from '@/constants/knowledge';

interface SourcePreviewClientWrapperProps {
  source: Source;
  sessionToken: string;
}

/**
 * Client component for the Source Preview page
 * Handles displaying source content and managing interactive features
 */
export default function SourcePreviewClientWrapper({
  source,
  sessionToken,
}: SourcePreviewClientWrapperProps) {
  const [content] = useState<string>(source.content || '');
  const [isContentExpanded, setIsContentExpanded] = useState(false);
  const notifications = useNotifications();
  const theme = useTheme();
  const [isEditingName, setIsEditingName] = useState(false);
  const [isEditingDescription, setIsEditingDescription] = useState(false);
  const [editedName, setEditedName] = useState(source.title || '');
  const [editedDescription, setEditedDescription] = useState(
    source.description || ''
  );
  const [isUpdating, setIsUpdating] = useState(false);

  const handleCopyContentBlock = async () => {
    try {
      await navigator.clipboard.writeText(content);
      notifications.show('Content copied to clipboard', {
        severity: 'success',
        autoHideDuration: 2000,
      });
    } catch (error) {
      notifications.show('Failed to copy content', {
        severity: 'error',
        autoHideDuration: 2000,
      });
    }
  };

  const handleEditName = () => {
    setIsEditingName(true);
    setEditedName(source.title || '');
  };

  const handleEditDescription = () => {
    setIsEditingDescription(true);
    setEditedDescription(source.description || '');
  };

  const handleCancelNameEdit = () => {
    setIsEditingName(false);
    setEditedName(source.title || '');
  };

  const handleCancelDescriptionEdit = () => {
    setIsEditingDescription(false);
    setEditedDescription(source.description || '');
  };

  const handleSaveNameEdit = async () => {
    if (!sessionToken) return;

    setIsUpdating(true);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const sourcesClient = clientFactory.getSourcesClient();

      await sourcesClient.updateSource(source.id, {
        title: editedName,
      });

      // Update the source object to reflect the new title
      source.title = editedName;
      setIsEditingName(false);

      notifications.show('Name updated successfully!', {
        severity: 'success',
        autoHideDuration: 2000,
      });
    } catch (error) {
      notifications.show('Failed to update name', {
        severity: 'error',
        autoHideDuration: 2000,
      });
      // Reset the edited name to the original value on error
      setEditedName(source.title || '');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleSaveDescriptionEdit = async () => {
    if (!sessionToken) return;

    setIsUpdating(true);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const sourcesClient = clientFactory.getSourcesClient();

      await sourcesClient.updateSource(source.id, {
        description: editedDescription,
      });

      // Update the source object to reflect the new description
      source.description = editedDescription;
      setIsEditingDescription(false);

      notifications.show('Description updated successfully!', {
        severity: 'success',
        autoHideDuration: 2000,
      });
    } catch (error) {
      notifications.show('Failed to update description', {
        severity: 'error',
        autoHideDuration: 2000,
      });
      // Reset the edited description to the original value on error
      setEditedDescription(source.description || '');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDownloadFile = async () => {
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const sourcesClient = clientFactory.getSourcesClient();

      // Get file content as blob to preserve binary data
      const blob = await sourcesClient.getSourceContentBlob(source.id);

      // Create download link with proper filename
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = source.source_metadata?.original_filename || source.title;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      notifications.show('File downloaded successfully', {
        severity: 'success',
        autoHideDuration: 2000,
      });
    } catch (error) {
      notifications.show('Failed to download file', {
        severity: 'error',
        autoHideDuration: 2000,
      });
    }
  };

  const fileExtension = getFileExtension(
    source.source_metadata?.original_filename
  );
  const displayTitle = truncateFilename(source.title);

  return (
    <PageContainer
      title={displayTitle}
      breadcrumbs={[
        { title: 'Knowledge', path: '/knowledge' },
        { title: displayTitle, path: `/knowledge/${source.id}` },
      ]}
    >
      {/* Source Detail */}
      <Paper elevation={2} sx={{ p: 3, mb: 4 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Source Detail
        </Typography>

        {/* Action Buttons */}
        <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleDownloadFile}
          >
            Download File
          </Button>
        </Box>

        {/* Title Field */}
        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
          Title
        </Typography>
        {isEditingName ? (
          <TextField
            fullWidth
            value={editedName}
            onChange={e => setEditedName(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSaveNameEdit();
              }
            }}
            sx={{ mb: 2 }}
            autoFocus
          />
        ) : (
          <Box sx={{ position: 'relative', mb: 3 }}>
            <Typography
              component="pre"
              variant="body2"
              sx={{
                whiteSpace: 'pre-wrap',
                fontFamily: 'monospace',
                bgcolor: 'action.hover',
                borderRadius: theme => theme.shape.borderRadius * 0.25,
                padding: 1,
                paddingRight: theme.spacing(10),
                wordBreak: 'break-word',
                minHeight: 'calc(2 * 1.4375em + 2 * 8px)',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {source.title || 'Untitled Source'}
            </Typography>
            <Button
              startIcon={<EditIcon />}
              onClick={handleEditName}
              sx={{
                position: 'absolute',
                top: 8,
                right: 8,
                zIndex: 1,
                backgroundColor: theme =>
                  theme.palette.mode === 'dark'
                    ? 'rgba(0, 0, 0, 0.6)'
                    : 'rgba(255, 255, 255, 0.8)',
                '&:hover': {
                  backgroundColor: theme =>
                    theme.palette.mode === 'dark'
                      ? 'rgba(0, 0, 0, 0.8)'
                      : 'rgba(255, 255, 255, 0.9)',
                },
              }}
            >
              Edit
            </Button>
          </Box>
        )}

        {/* Name Edit Actions */}
        {isEditingName && (
          <Box
            sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mb: 3 }}
          >
            <Button
              variant="outlined"
              onClick={handleCancelNameEdit}
              disabled={isUpdating}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={handleSaveNameEdit}
              disabled={isUpdating}
            >
              {isUpdating ? 'Saving...' : 'Save'}
            </Button>
          </Box>
        )}

        {/* Description Field */}
        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
          Description
        </Typography>
        {isEditingDescription ? (
          <TextField
            fullWidth
            multiline
            rows={4}
            value={editedDescription}
            onChange={e => setEditedDescription(e.target.value)}
            sx={{ mb: 2 }}
            autoFocus
          />
        ) : (
          <Box sx={{ position: 'relative', mb: 3 }}>
            <Typography
              component="pre"
              variant="body2"
              sx={{
                whiteSpace: 'pre-wrap',
                fontFamily: 'monospace',
                bgcolor: 'action.hover',
                borderRadius: theme => theme.shape.borderRadius * 0.25,
                padding: 1,
                minHeight: 'calc(4 * 1.4375em + 2 * 8px)',
                paddingRight: theme.spacing(10),
                wordBreak: 'break-word',
              }}
            >
              {source.description || ' '}
            </Typography>
            <Button
              startIcon={<EditIcon />}
              onClick={handleEditDescription}
              sx={{
                position: 'absolute',
                top: 8,
                right: 8,
                zIndex: 1,
                backgroundColor: theme =>
                  theme.palette.mode === 'dark'
                    ? 'rgba(0, 0, 0, 0.6)'
                    : 'rgba(255, 255, 255, 0.8)',
                '&:hover': {
                  backgroundColor: theme =>
                    theme.palette.mode === 'dark'
                      ? 'rgba(0, 0, 0, 0.8)'
                      : 'rgba(255, 255, 255, 0.9)',
                },
              }}
            >
              Edit
            </Button>
          </Box>
        )}

        {/* Description Edit Actions */}
        {isEditingDescription && (
          <Box
            sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mb: 3 }}
          >
            <Button
              variant="outlined"
              onClick={handleCancelDescriptionEdit}
              disabled={isUpdating}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={handleSaveDescriptionEdit}
              disabled={isUpdating}
            >
              {isUpdating ? 'Saving...' : 'Save'}
            </Button>
          </Box>
        )}

        {/* Metadata Grid */}
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 2,
            mb: 2,
          }}
        >
          <Box>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mb: 0.5 }}
            >
              Size:
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {formatFileSize(source.source_metadata?.file_size)}
            </Typography>
          </Box>
          <Box>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mb: 0.5 }}
            >
              Type:
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {fileExtension.toUpperCase()}
            </Typography>
          </Box>
          <Box>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mb: 0.5 }}
            >
              Added by:
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {source.user?.name || source.user?.email || 'Unknown'}
            </Typography>
          </Box>
          <Box>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mb: 0.5 }}
            >
              Uploaded:
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {formatDate(source.created_at)}
            </Typography>
          </Box>
        </Box>
      </Paper>

      {/* Content preview */}
      {content ? (
        <Paper elevation={2} sx={{ p: 3, mb: 4 }}>
          <Box className={styles.contentBlock}>
            {/* Content Block Header */}
            <Box className={styles.contentBlockHeader}>
              <Box className={styles.contentBlockTitle}>
                <InsertDriveFileOutlined className={styles.documentIcon} />
                <Typography variant="body2" color="text.secondary">
                  Extracted Content
                </Typography>
              </Box>
              <Box className={styles.contentBlockActions}>
                <Tooltip title="Copy Content">
                  <IconButton
                    size="small"
                    onClick={handleCopyContentBlock}
                    className={styles.copyButton}
                  >
                    <ContentCopyIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title={isContentExpanded ? 'Collapse' : 'Expand'}>
                  <IconButton
                    size="small"
                    onClick={() => setIsContentExpanded(!isContentExpanded)}
                    className={styles.expandButton}
                  >
                    {isContentExpanded ? (
                      <ExpandLessIcon />
                    ) : (
                      <ExpandMoreIcon />
                    )}
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>

            {/* Content Block Body */}
            <Collapse in={isContentExpanded}>
              <Box className={styles.contentBlockBody}>
                <pre className={styles.contentText}>{content}</pre>
              </Box>
            </Collapse>
          </Box>
        </Paper>
      ) : (
        <Box className={styles.emptyContainer}>
          <Typography color="text.secondary">No content available</Typography>
        </Box>
      )}
    </PageContainer>
  );
}
