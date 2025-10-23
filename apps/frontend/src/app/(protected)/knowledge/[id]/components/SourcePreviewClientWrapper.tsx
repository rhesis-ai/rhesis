'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Alert,
  Paper,
  Button,
  Chip,
  IconButton,
  Tooltip,
  Collapse,
} from '@mui/material';
import { Source } from '@/utils/api-client/interfaces/source';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DownloadIcon from '@mui/icons-material/Download';
import CloseIcon from '@mui/icons-material/Close';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import styles from '@/styles/SourcePreview.module.css';

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
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isContentExpanded, setIsContentExpanded] = useState(false);
  const notifications = useNotifications();

  useEffect(() => {
    // Simply use the existing content from the source object
    if (source.content && source.content.trim()) {
      setContent(source.content);
    } else {
      setContent('');
    }
    setLoading(false);
  }, [source.content]);

  const handleCopyContentBlock = async () => {
    try {
      await navigator.clipboard.writeText(content);
      notifications.show('Content copied to clipboard', {
        severity: 'success',
        autoHideDuration: 2000,
      });
    } catch (error) {
      console.error('Failed to copy content:', error);
      notifications.show('Failed to copy content', {
        severity: 'error',
        autoHideDuration: 2000,
      });
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
      console.error('Failed to download file:', error);
      notifications.show('Failed to download file', {
        severity: 'error',
        autoHideDuration: 2000,
      });
    }
  };

  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return 'Unknown';
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return 'Invalid date';

      // Use consistent DD/MM/YYYY formatting
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');

      return `${day}/${month}/${year}`;
    } catch {
      return 'Invalid date';
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'Unknown';
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${Math.round((bytes / Math.pow(1024, i)) * 100) / 100} ${sizes[i]}`;
  };

  const getFileExtension = (filename?: string) => {
    if (!filename) return 'unknown';
    const ext = filename.split('.').pop()?.toLowerCase();
    return ext || 'unknown';
  };
  const truncateFilename = (filename: string, maxLength: number = 50) => {
    if (filename.length <= maxLength) return filename;

    // Try to preserve the file extension
    const lastDotIndex = filename.lastIndexOf('.');
    if (lastDotIndex > 0) {
      const extension = filename.substring(lastDotIndex);
      const nameWithoutExt = filename.substring(0, lastDotIndex);
      const availableLength = maxLength - extension.length - 3; // 3 for "..."

      if (availableLength > 0) {
        return `${nameWithoutExt.substring(0, availableLength)}...${extension}`;
      }
    }

    // Fallback: just truncate and add ellipsis
    return `${filename.substring(0, maxLength - 3)}...`;
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
      {/* Header with source info and actions */}
      <Paper className={styles.headerContainer}>
        <Box className={styles.headerContent}>
          <Box className={styles.sourceInfo}>
            {/* Action Buttons */}
            <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
              <Button
                variant="contained"
                color="primary"
                startIcon={<DownloadIcon />}
                onClick={handleDownloadFile}
              >
                Download File
              </Button>
            </Box>

            {source.description && (
              <Typography
                variant="body2"
                color="text.secondary"
                className={styles.description}
              >
                {source.description}
              </Typography>
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
                  {source.source_metadata?.uploader_name || 'Unknown'}
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
                  {formatDate(source.source_metadata?.uploaded_at)}
                </Typography>
              </Box>
            </Box>
          </Box>
        </Box>
      </Paper>

      {/* Content preview */}
      {loading && (
        <Box className={styles.loadingContainer}>
          <Typography color="text.secondary">Loading content...</Typography>
        </Box>
      )}

      {error && (
        <Alert severity="error" className={styles.errorAlert}>
          {error}
        </Alert>
      )}

      {!loading && !error && content && (
        <Box className={styles.contentBlock}>
          {/* Content Block Header */}
          <Box className={styles.contentBlockHeader}>
            <Box className={styles.contentBlockTitle}>
              <InsertDriveFileOutlined className={styles.documentIcon} />
              <Typography variant="body2" color="text.secondary">
                {source.title || 'Document Content'}
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
                  {isContentExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
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
      )}

      {!loading && !error && !content && (
        <Box className={styles.emptyContainer}>
          <Typography color="text.secondary">No content available</Typography>
        </Box>
      )}
    </PageContainer>
  );
}
