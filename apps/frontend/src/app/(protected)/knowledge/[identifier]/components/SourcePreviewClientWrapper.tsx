'use client';

import React, { useState, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  IconButton,
  Tooltip,
  useTheme,
  TextField,
  Stack,
  Collapse,
  Avatar,
} from '@mui/material';
import { Source } from '@/utils/api-client/interfaces/source';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import DownloadIcon from '@mui/icons-material/Download';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import EditIcon from '@mui/icons-material/Edit';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CancelIcon from '@mui/icons-material/Cancel';
import CheckIcon from '@mui/icons-material/Check';
import InfoIcon from '@mui/icons-material/Info';
import ArticleIcon from '@mui/icons-material/Article';
import {
  formatFileSize,
  formatDate,
  getFileExtension,
  truncateFilename,
} from '@/constants/knowledge';
import SourceTags from './SourceTags';
import CommentsWrapper from '@/components/comments/CommentsWrapper';

interface SourcePreviewClientWrapperProps {
  source: Source;
  sessionToken: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

type EditableSectionType = 'general';

interface EditData {
  title?: string;
  description?: string;
}

/**
 * Client component for the Source Preview page
 * Handles displaying source content and managing interactive features
 */
export default function SourcePreviewClientWrapper({
  source,
  sessionToken,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: SourcePreviewClientWrapperProps) {
  const [content] = useState<string>(source.content || '');
  const [isContentExpanded, setIsContentExpanded] = useState(!!source.content);
  const notifications = useNotifications();
  const theme = useTheme();
  const [isEditing, setIsEditing] = useState<EditableSectionType | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Refs for uncontrolled text fields
  const titleRef = useRef<HTMLInputElement>(null);
  const descriptionRef = useRef<HTMLTextAreaElement>(null);

  const displayTitle = truncateFilename(source.title);

  // Determine the type to display
  const getDisplayType = (): string | null => {
    // First check source_metadata.source_type (for MCP imports like Notion)
    if (source.source_metadata?.source_type) {
      return source.source_metadata.source_type;
    }

    // Check if this is a Tool source type (MCP/API imports)
    if (
      source.source_type?.type_value === 'Tool' &&
      source.source_metadata?.provider
    ) {
      // Capitalize the provider name (e.g., "notion" -> "Notion")
      return (
        source.source_metadata.provider.charAt(0).toUpperCase() +
        source.source_metadata.provider.slice(1)
      );
    }

    // Fall back to file extension for document sources
    const fileExtension = getFileExtension(
      source.source_metadata?.original_filename
    );

    // Return null if no valid type found
    if (fileExtension === 'unknown') {
      return null;
    }

    return fileExtension.toUpperCase();
  };

  const displayType = getDisplayType();
  const hasSize = source.source_metadata?.file_size != null;
  const hasType = displayType != null;

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

  const handleEdit = useCallback(
    (section: EditableSectionType) => {
      setIsEditing(section);
      // Populate refs with current values when entering edit mode
      if (section === 'general') {
        if (titleRef.current) {
          titleRef.current.value = source.title || '';
        }
        if (descriptionRef.current) {
          descriptionRef.current.value = source.description || '';
        }
      }
    },
    [source]
  );

  const handleCancelEdit = useCallback(() => {
    setIsEditing(null);
  }, []);

  // Helper function to collect current field values without triggering re-renders
  const collectFieldValues = useCallback((): Partial<EditData> => {
    const values: Partial<EditData> = {};

    if (titleRef.current) values.title = titleRef.current.value;
    if (descriptionRef.current)
      values.description = descriptionRef.current.value;

    return values;
  }, []);

  const handleConfirmEdit = useCallback(async () => {
    if (!sessionToken) return;

    setIsSaving(true);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const sourcesClient = clientFactory.getSourcesClient();

      // Collect values from refs
      const fieldValues = collectFieldValues();

      await sourcesClient.updateSource(source.id, {
        title: fieldValues.title,
        description: fieldValues.description,
      });

      // Update the source object to reflect changes
      source.title = fieldValues.title || source.title;
      source.description = fieldValues.description || source.description;
      setIsEditing(null);

      notifications.show('Source updated successfully', {
        severity: 'success',
      });
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to update source';
      notifications.show(errorMessage, { severity: 'error' });
    } finally {
      setIsSaving(false);
    }
  }, [sessionToken, source, collectFieldValues, notifications]);

  // EditableSection component
  const EditableSection = React.memo(
    ({
      title,
      icon,
      section,
      children,
      isEditing,
      onEdit,
      onCancel,
      onConfirm,
      isSaving,
    }: {
      title: string;
      icon: React.ReactNode;
      section: EditableSectionType;
      children: React.ReactNode;
      isEditing: EditableSectionType | null;
      onEdit: (section: EditableSectionType) => void;
      onCancel: () => void;
      onConfirm: () => void;
      isSaving?: boolean;
    }) => {
      return (
        <Paper
          sx={{
            p: theme.spacing(3),
            position: 'relative',
            borderRadius: theme.spacing(1),
            bgcolor: theme.palette.background.paper,
            boxShadow: theme.shadows[1],
          }}
        >
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: theme.spacing(3),
              pb: theme.spacing(2),
              borderBottom: `1px solid ${theme.palette.divider}`,
            }}
          >
            <SectionHeader title={title} />
            <Box sx={{ display: 'flex', gap: 1 }}>
              {section === 'general' && !isEditing && (
                <Button
                  startIcon={<DownloadIcon />}
                  onClick={handleDownloadFile}
                  variant="outlined"
                  size="small"
                  sx={{
                    color: theme.palette.text.secondary,
                    borderColor: theme.palette.divider,
                    '&:hover': {
                      borderColor: theme.palette.text.secondary,
                    },
                  }}
                >
                  Download
                </Button>
              )}
              {!isEditing && (
                <Button
                  startIcon={<EditIcon />}
                  onClick={() => onEdit(section)}
                  variant="outlined"
                  size="small"
                  sx={{
                    color: theme.palette.primary.main,
                    borderColor: theme.palette.primary.main,
                    '&:hover': {
                      backgroundColor: theme.palette.primary.light,
                      borderColor: theme.palette.primary.main,
                    },
                  }}
                >
                  Edit Section
                </Button>
              )}
            </Box>
          </Box>

          {isEditing === section ? (
            <Box>
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: theme.spacing(3),
                  p: theme.spacing(2),
                  bgcolor: theme.palette.action.hover,
                  borderRadius: theme.spacing(0.5),
                  mb: theme.spacing(3),
                  border: `1px solid ${theme.palette.divider}`,
                }}
              >
                {children}
              </Box>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: theme.spacing(1),
                  mt: theme.spacing(2),
                }}
              >
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<CancelIcon />}
                  onClick={onCancel}
                  disabled={isSaving}
                  sx={{
                    borderColor: theme.palette.error.main,
                    '&:hover': {
                      backgroundColor: theme.palette.error.light,
                      borderColor: theme.palette.error.main,
                    },
                  }}
                >
                  Cancel
                </Button>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<CheckIcon />}
                  onClick={onConfirm}
                  disabled={isSaving}
                  sx={{
                    bgcolor: theme.palette.primary.main,
                    '&:hover': {
                      bgcolor: theme.palette.primary.dark,
                    },
                  }}
                >
                  {isSaving ? 'Saving...' : 'Save Section'}
                </Button>
              </Box>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {children}
            </Box>
          )}
        </Paper>
      );
    }
  );

  EditableSection.displayName = 'EditableSection';

  const SectionHeader = React.memo(({ title }: { title: string }) => {
    const theme = useTheme();
    return (
      <Typography
        variant="h6"
        sx={{
          fontWeight: theme.typography.fontWeightMedium,
          color: theme.palette.text.primary,
        }}
      >
        {title}
      </Typography>
    );
  });

  SectionHeader.displayName = 'SectionHeader';

  const InfoRow = React.memo(
    ({ label, children }: { label: string; children: React.ReactNode }) => {
      const theme = useTheme();
      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: theme.spacing(1),
            py: theme.spacing(1),
          }}
        >
          <Typography
            variant="subtitle2"
            sx={{
              color: theme.palette.text.secondary,
              fontWeight: theme.typography.fontWeightMedium,
              letterSpacing: '0.02em',
            }}
          >
            {label}
          </Typography>
          <Box
            sx={{
              '& .MuiTypography-root': {
                color: theme.palette.text.primary,
              },
            }}
          >
            {children}
          </Box>
        </Box>
      );
    }
  );

  InfoRow.displayName = 'InfoRow';

  return (
    <PageContainer
      title={displayTitle}
      breadcrumbs={[
        { title: 'Knowledge', path: '/knowledge' },
        { title: displayTitle, path: `/knowledge/${source.id}` },
      ]}
    >
      <Stack direction="column" spacing={3}>
        {/* Source Information Section - Single Paper */}
        <Paper
          sx={{
            p: theme.spacing(3),
            borderRadius: theme.spacing(1),
            bgcolor: theme.palette.background.paper,
            boxShadow: theme.shadows[1],
          }}
        >
          {/* Header */}
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: theme.spacing(3),
              pb: theme.spacing(2),
              borderBottom: `1px solid ${theme.palette.divider}`,
            }}
          >
            <SectionHeader title="Source Information" />
            <Box sx={{ display: 'flex', gap: 1 }}>
              {!isEditing && (
                <>
                  <Button
                    startIcon={<DownloadIcon />}
                    onClick={handleDownloadFile}
                    variant="outlined"
                    size="small"
                    sx={{
                      color: theme.palette.text.secondary,
                      borderColor: theme.palette.divider,
                      '&:hover': {
                        borderColor: theme.palette.text.secondary,
                      },
                    }}
                  >
                    Download
                  </Button>
                  <Button
                    startIcon={<EditIcon />}
                    onClick={() => handleEdit('general')}
                    variant="outlined"
                    size="small"
                    sx={{
                      color: theme.palette.primary.main,
                      borderColor: theme.palette.primary.main,
                      '&:hover': {
                        backgroundColor: theme.palette.primary.light,
                        borderColor: theme.palette.primary.main,
                      },
                    }}
                  >
                    Edit Section
                  </Button>
                </>
              )}
            </Box>
          </Box>

          {/* Editable Content */}
          {isEditing === 'general' ? (
            <Box>
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: theme.spacing(3),
                  p: theme.spacing(2),
                  bgcolor: theme.palette.action.hover,
                  borderRadius: theme.spacing(0.5),
                  mb: theme.spacing(3),
                  border: `1px solid ${theme.palette.divider}`,
                }}
              >
                <InfoRow label="Title">
                  <TextField
                    key={`title-${source.id}`}
                    fullWidth
                    required
                    inputRef={titleRef}
                    defaultValue={source.title || ''}
                    placeholder="Enter source title"
                  />
                </InfoRow>

                <InfoRow label="Description">
                  <TextField
                    key={`description-${source.id}`}
                    fullWidth
                    multiline
                    rows={4}
                    inputRef={descriptionRef}
                    defaultValue={source.description || ''}
                    placeholder="Enter source description"
                  />
                </InfoRow>
              </Box>

              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: theme.spacing(1),
                  mb: theme.spacing(3),
                }}
              >
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<CancelIcon />}
                  onClick={handleCancelEdit}
                  disabled={isSaving}
                  sx={{
                    borderColor: theme.palette.error.main,
                    '&:hover': {
                      backgroundColor: theme.palette.error.light,
                      borderColor: theme.palette.error.main,
                    },
                  }}
                >
                  Cancel
                </Button>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<CheckIcon />}
                  onClick={handleConfirmEdit}
                  disabled={isSaving}
                  sx={{
                    bgcolor: theme.palette.primary.main,
                    '&:hover': {
                      bgcolor: theme.palette.primary.dark,
                    },
                  }}
                >
                  {isSaving ? 'Saving...' : 'Save Section'}
                </Button>
              </Box>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <InfoRow label="Title">
                <Typography>{source.title || 'Untitled Source'}</Typography>
              </InfoRow>

              <InfoRow label="Description">
                <Typography>{source.description || '-'}</Typography>
              </InfoRow>
            </Box>
          )}

          {/* Metadata - always visible below editable content */}
          {!isEditing && (
            <>
              <Box
                sx={{
                  borderTop: `1px solid ${theme.palette.divider}`,
                  pt: theme.spacing(3),
                  mt: theme.spacing(3),
                }}
              />
              <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap', mb: 3 }}>
                {hasSize && (
                  <InfoRow label="Size">
                    <Typography variant="body1" color="text.primary">
                      {formatFileSize(source.source_metadata?.file_size)}
                    </Typography>
                  </InfoRow>
                )}

                {hasType && (
                  <InfoRow label="Type">
                    <Typography variant="body1" color="text.primary">
                      {displayType}
                    </Typography>
                  </InfoRow>
                )}

                <InfoRow label="Added by">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Avatar
                      src={source.user?.picture}
                      alt={source.user?.name || source.user?.email || 'Unknown'}
                      sx={{
                        width: 24,
                        height: 24,
                        fontSize: theme => theme.typography.caption.fontSize,
                      }}
                    >
                      {(source.user?.name || source.user?.email || 'U')
                        .charAt(0)
                        .toUpperCase()}
                    </Avatar>
                    <Typography variant="body1" color="text.primary">
                      {source.user?.name || source.user?.email || 'Unknown'}
                    </Typography>
                  </Box>
                </InfoRow>

                <InfoRow label="Added on">
                  <Typography variant="body1" color="text.primary">
                    {formatDate(source.created_at)}
                  </Typography>
                </InfoRow>
              </Box>
            </>
          )}

          {/* Tags - always visible at bottom */}
          <InfoRow label="Tags">
            <SourceTags
              sessionToken={sessionToken}
              source={source}
              disableEdition={isEditing === 'general'}
            />
          </InfoRow>
        </Paper>

        {/* Extracted Content Section */}
        {content && (
          <Paper
            sx={{
              p: theme.spacing(3),
              borderRadius: theme.spacing(1),
              bgcolor: theme.palette.background.paper,
              boxShadow: theme.shadows[1],
            }}
          >
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: isContentExpanded ? theme.spacing(3) : 0,
                pb: isContentExpanded ? theme.spacing(2) : 0,
                borderBottom: isContentExpanded
                  ? `1px solid ${theme.palette.divider}`
                  : 'none',
                cursor: 'pointer',
                '&:hover': {
                  '& .expand-icon': {
                    color: theme.palette.primary.main,
                  },
                },
              }}
              onClick={() => setIsContentExpanded(!isContentExpanded)}
            >
              <SectionHeader title="Extracted Content" />
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <Tooltip title="Copy Content">
                  <IconButton
                    size="small"
                    onClick={e => {
                      e.stopPropagation();
                      handleCopyContentBlock();
                    }}
                    sx={{ color: theme.palette.text.secondary }}
                  >
                    <ContentCopyIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <IconButton
                  size="small"
                  className="expand-icon"
                  sx={{
                    color: theme.palette.text.secondary,
                    transition: 'transform 0.3s, color 0.2s',
                    transform: isContentExpanded
                      ? 'rotate(180deg)'
                      : 'rotate(0deg)',
                  }}
                >
                  <ExpandMoreIcon />
                </IconButton>
              </Box>
            </Box>

            <Collapse in={isContentExpanded}>
              <Box
                sx={{
                  bgcolor: theme.palette.action.hover,
                  borderRadius: theme.spacing(0.5),
                  maxHeight: 400,
                  overflow: 'auto',
                  mt: theme.spacing(2),
                }}
              >
                <Typography
                  component="pre"
                  sx={{
                    m: 0,
                    p: 2,
                    fontFamily: 'Monaco, Menlo, Ubuntu Mono, monospace',
                    fontSize: theme => theme.typography.body2.fontSize,
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    color: theme.palette.text.primary,
                  }}
                >
                  {content}
                </Typography>
              </Box>
            </Collapse>
          </Paper>
        )}

        {/* Comments Section */}
        <Paper
          sx={{
            p: theme.spacing(3),
            borderRadius: theme.spacing(1),
            bgcolor: theme.palette.background.paper,
            boxShadow: theme.shadows[1],
          }}
        >
          <CommentsWrapper
            entityType="Source"
            entityId={source.id}
            sessionToken={sessionToken}
            currentUserId={currentUserId}
            currentUserName={currentUserName}
            currentUserPicture={currentUserPicture}
          />
        </Paper>
      </Stack>
    </PageContainer>
  );
}
