'use client';

import React, { useState, useEffect } from 'react';
import { Box, Typography, Alert, Paper, Button, Chip, IconButton, Tooltip, ToggleButton, ToggleButtonGroup, Collapse } from '@mui/material';
import { Source } from '@/utils/api-client/interfaces/source';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DownloadIcon from '@mui/icons-material/Download';
import CloseIcon from '@mui/icons-material/Close';
import FormatAlignLeftIcon from '@mui/icons-material/FormatAlignLeft';
import CodeIcon from '@mui/icons-material/Code';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import { useRouter } from 'next/navigation';
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
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<'formatted' | 'raw'>('formatted');
  const [isContentExpanded, setIsContentExpanded] = useState(false);
  const notifications = useNotifications();
  const router = useRouter();

  useEffect(() => {
    const fetchContent = async () => {
      try {
        setLoading(true);
        setError(null);

        const clientFactory = new ApiClientFactory(sessionToken);
        const sourcesClient = clientFactory.getSourcesClient();

        // Try to get extracted content first (processed markdown)
        try {
          console.log('Attempting to extract content for source:', source.id);
          const extractedData = await sourcesClient.extractSourceContent(source.id);
          console.log('Extraction successful:', extractedData);
          setContent(extractedData.content || '');
        } catch (extractError) {
          // Fallback to raw content if extraction fails
          console.warn('Extraction failed, falling back to raw content:', extractError);
          try {
            console.log('Attempting to get raw content for source:', source.id);
            const rawContent = await sourcesClient.getSourceContent(source.id);
            console.log('Raw content successful:', rawContent.substring(0, 100) + '...');
            setContent(rawContent);
          } catch (rawError) {
            console.error('Both extraction and raw content failed:', rawError);
            throw rawError;
          }
        }
      } catch (error) {
        console.error('Error fetching source content:', error);
        setError('Failed to load source content');
      } finally {
        setLoading(false);
      }
    };

    fetchContent();
  }, [source.id, sessionToken]);

  const handleCopyText = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      notifications.show('Content copied to clipboard', {
        severity: 'success',
        autoHideDuration: 2000,
      });
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy text:', error);
      notifications.show('Failed to copy content', {
        severity: 'error',
        autoHideDuration: 2000,
      });
    }
  };

  const handleCopyContentBlock = async () => {
    const contentToCopy = viewMode === 'formatted' ? formattedContent : content;
    try {
      await navigator.clipboard.writeText(contentToCopy);
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

      // Get raw file content for download
      const response = await sourcesClient.getSourceContent(source.id);

      // Create blob and download
      const blob = new Blob([response], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = source.source_metadata?.original_filename || `${source.title}.txt`;
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

  const handleGoBack = () => {
    router.back();
  };

  const handleViewModeChange = (
    event: React.MouseEvent<HTMLElement>,
    newViewMode: 'formatted' | 'raw' | null,
  ) => {
    if (newViewMode !== null) {
      setViewMode(newViewMode);
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
    if (!ext) return 'unknown';
    return ext === 'htm' ? 'html' : ext === 'jpeg' ? 'jpg' : ext;
  };

  const fileExtension = getFileExtension(source.source_metadata?.original_filename);

  // Convert \n to actual line breaks for display and handle markdown-like formatting
  const formattedContent = content
    .replace(/\\n/g, '\n')
    .replace(/\*\*(.*?)\*\*/g, '**$1**') // Keep bold formatting visible
    .replace(/\*(.*?)\*/g, '*$1*') // Keep italic formatting visible
    .replace(/#{1,6}\s/g, (match) => match.trim() + ' ') // Clean up headers
    .trim();

  return (
    <PageContainer
      title="Source Preview"
      breadcrumbs={[
        { title: 'Knowledge', path: '/knowledge' },
        { title: source.title, path: `/knowledge/${source.id}` },
      ]}
    >
      {/* Header with source info and actions */}
      <Paper className={styles.headerContainer}>
        <Box className={styles.headerContent}>
          <Box className={styles.sourceInfo}>
            <Box className={styles.titleRow}>
              <Typography variant="h5" className={styles.sourceTitle}>
                {source.title}
              </Typography>
              <Chip
                label={fileExtension.toUpperCase()}
                size="small"
                variant="outlined"
                className={styles.fileTypeChip}
              />
            </Box>

            {source.description && (
              <Typography variant="body2" color="text.secondary" className={styles.description}>
                {source.description}
              </Typography>
            )}

            <Box className={styles.metadataRow}>
              <Typography variant="caption" color="text.secondary">
                Uploaded: {formatDate(source.source_metadata?.uploaded_at)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Size: {formatFileSize(source.source_metadata?.file_size)}
              </Typography>
              {source.source_metadata?.uploader_name && (
                <Box className={styles.ownerContainer}>
                  <Typography variant="caption" color="text.secondary">
                    Added by: {source.source_metadata.uploader_name}
                  </Typography>
                </Box>
              )}
              {source.tags && source.tags.length > 0 && (
                <Box className={styles.tagsContainer}>
                  <Typography variant="caption" color="text.secondary">
                    Tags: {source.tags.join(', ')}
                  </Typography>
                </Box>
              )}
            </Box>
          </Box>

          <Box className={styles.actionButtons}>
            <Button
              variant="outlined"
              startIcon={<ArrowBackIcon />}
              onClick={handleGoBack}
              size="small"
            >
              Back
            </Button>
            <Button
              variant="outlined"
              startIcon={<ContentCopyIcon />}
              onClick={handleCopyText}
              disabled={!content}
              size="small"
            >
              Copy Text
            </Button>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              onClick={handleDownloadFile}
              disabled={!content}
              size="small"
            >
              Download File
            </Button>
          </Box>
        </Box>
      </Paper>

      {/* Content preview */}
      <Paper className={styles.contentContainer}>
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
                <ToggleButtonGroup
                  value={viewMode}
                  exclusive
                  onChange={handleViewModeChange}
                  size="small"
                  aria-label="view mode"
                >
                  <ToggleButton value="formatted" aria-label="formatted view">
                    <FormatAlignLeftIcon fontSize="small" />
                    <Typography variant="caption" sx={{ ml: 0.5 }}>
                      Formatted
                    </Typography>
                  </ToggleButton>
                  <ToggleButton value="raw" aria-label="raw view">
                    <CodeIcon fontSize="small" />
                    <Typography variant="caption" sx={{ ml: 0.5 }}>
                      Raw
                    </Typography>
                  </ToggleButton>
                </ToggleButtonGroup>
                <Tooltip title="Copy Content">
                  <IconButton
                    size="small"
                    onClick={handleCopyContentBlock}
                    className={styles.copyButton}
                  >
                    <ContentCopyIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title={isContentExpanded ? "Collapse" : "Expand"}>
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
                <pre className={styles.contentText}>
                  {viewMode === 'formatted' ? formattedContent : content}
                </pre>
              </Box>
            </Collapse>
          </Box>
        )}

        {!loading && !error && !content && (
          <Box className={styles.emptyContainer}>
            <Typography color="text.secondary">No content available</Typography>
          </Box>
        )}
      </Paper>
    </PageContainer>
  );
}
