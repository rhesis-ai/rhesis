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
  CircularProgress,
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
import RefreshIcon from '@mui/icons-material/Refresh';
import { useRouter } from 'next/navigation';
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
  const [localSource, setLocalSource] = useState<Source>(source);
  const [content, setContent] = useState<string>(localSource.content || '');
  const [isContentExpanded, setIsContentExpanded] = useState(
    !!localSource.content
  );
  const notifications = useNotifications();
  const theme = useTheme();
  const [isEditing, setIsEditing] = useState<EditableSectionType | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const router = useRouter();

  // Refs for uncontrolled text fields
  const titleRef = useRef<HTMLInputElement>(null);
  const descriptionRef = useRef<HTMLInputElement>(null);

  const displayTitle = truncateFilename(localSource.title);

  // Determine the type to display
  const getDisplayType = (): string | null => {
    // First check source_metadata.source_type (for MCP imports like Notion)
    if (localSource.source_metadata?.source_type) {
      return localSource.source_metadata.source_type;
    }

    // Check if this is a Tool source type (MCP/API imports)
    if (
      localSource.source_type?.type_value === 'Tool' &&
      localSource.source_metadata?.provider
    ) {
      // Capitalize the provider name (e.g., "notion" -> "Notion")
      return (
        localSource.source_metadata.provider.charAt(0).toUpperCase() +
        localSource.source_metadata.provider.slice(1)
      );
    }

    // Fall back to file extension for document sources
    const fileExtension = getFileExtension(
      localSource.source_metadata?.original_filename
    );

    // Return null if no valid type found
    if (fileExtension === 'unknown') {
      return null;
    }

    return fileExtension.toUpperCase();
  };

  const displayType = getDisplayType();
  const hasSize = localSource.source_metadata?.file_size != null;
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
      const blob = await sourcesClient.getSourceContentBlob(localSource.id);

      // Create download link with proper filename
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download =
        localSource.source_metadata?.original_filename || localSource.title;
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

  const handleUpdateFromMCP = async () => {
    if (!sessionToken || isUpdating) return;

    // Check if this is an MCP source
    if (localSource.source_type?.type_value !== 'Tool') {
      return;
    }

    const metadata = localSource.source_metadata || {};
    const mcpToolId = metadata.mcp_tool_id;
    const mcpId = metadata.mcp_id;
    const mcpUrl = metadata.url;

    if (!mcpToolId || (!mcpId && !mcpUrl)) {
      notifications.show('Missing MCP source information', {
        severity: 'error',
        autoHideDuration: 3000,
      });
      return;
    }

    setIsUpdating(true);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const servicesClient = clientFactory.getServicesClient();
      const sourcesClient = clientFactory.getSourcesClient();

      // Extract content from MCP
      const extractOptions: { url?: string; id?: string } = {};
      if (mcpUrl) {
        extractOptions.url = mcpUrl;
      } else if (mcpId) {
        extractOptions.id = mcpId;
      }

      const extractResult = await servicesClient.extractMCP(
        extractOptions,
        mcpToolId
      );

      // Update source with new content
      await sourcesClient.updateSource(localSource.id, {
        content: extractResult.content,
      });

      // Refetch updated source (refetch pattern - no useEffect sync needed)
      const updatedSource = await sourcesClient.getSourceWithContent(
        localSource.id
      );
      setLocalSource(updatedSource);
      setContent(updatedSource.content || '');

      // Refresh server component for page title, etc.
      router.refresh();

      notifications.show('Source updated successfully', {
        severity: 'success',
        autoHideDuration: 2000,
      });
    } catch (error: any) {
      // Handle 404 specifically (item not found)
      if (
        error?.status === 404 ||
        error?.data?.detail?.includes('404') ||
        error?.message?.includes('404')
      ) {
        const linkUrl = metadata.url || 'the link';
        notifications.show(
          `The source link (${linkUrl}) no longer works. The item may have been deleted or moved.`,
          {
            severity: 'error',
            autoHideDuration: 5000,
          }
        );
      } else {
        // Handle other errors normally
        const errorMessage =
          error instanceof Error
            ? error.message
            : error?.data?.detail || 'Failed to update source from MCP';
        notifications.show(errorMessage, {
          severity: 'error',
          autoHideDuration: 3000,
        });
      }
    } finally {
      setIsUpdating(false);
    }
  };

  const handleEdit = useCallback(
    (section: EditableSectionType) => {
      setIsEditing(section);
      // Populate refs with current values when entering edit mode
      if (section === 'general') {
        if (titleRef.current) {
          titleRef.current.value = localSource.title || '';
        }
        if (descriptionRef.current) {
          descriptionRef.current.value = localSource.description || '';
        }
      }
    },
    [localSource]
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

      await sourcesClient.updateSource(localSource.id, {
        title: fieldValues.title,
        description: fieldValues.description,
      });

      // Update local source state
      setLocalSource(prev => ({
        ...prev,
        title: fieldValues.title || prev.title,
        description: fieldValues.description || prev.description,
      }));
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
  }, [sessionToken, localSource, collectFieldValues, notifications]);

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
        { title: displayTitle, path: `/knowledge/${localSource.id}` },
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
                  {localSource.source_type?.type_value === 'Tool' ? (
                    <Button
                      startIcon={
                        isUpdating ? (
                          <CircularProgress size={16} />
                        ) : (
                          <RefreshIcon />
                        )
                      }
                      onClick={handleUpdateFromMCP}
                      variant="outlined"
                      size="small"
                      disabled={isUpdating}
                      sx={{
                        color: theme.palette.text.secondary,
                        borderColor: theme.palette.divider,
                        '&:hover': {
                          borderColor: theme.palette.text.secondary,
                        },
                        '&:disabled': {
                          opacity: 0.6,
                        },
                      }}
                    >
                      {isUpdating ? 'Updating...' : 'Update'}
                    </Button>
                  ) : (
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
                    key={`title-${localSource.id}`}
                    fullWidth
                    required
                    inputRef={titleRef}
                    defaultValue={localSource.title || ''}
                    placeholder="Enter source title"
                  />
                </InfoRow>

                <InfoRow label="Description">
                  <TextField
                    key={`description-${localSource.id}`}
                    fullWidth
                    multiline
                    rows={4}
                    inputRef={descriptionRef}
                    defaultValue={localSource.description || ''}
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
                <Typography>
                  {localSource.title || 'Untitled Source'}
                </Typography>
              </InfoRow>

              <InfoRow label="Description">
                <Typography>{localSource.description || '-'}</Typography>
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
                      {formatFileSize(localSource.source_metadata?.file_size)}
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
                      src={localSource.user?.picture}
                      alt={
                        localSource.user?.name ||
                        localSource.user?.email ||
                        'Unknown'
                      }
                      sx={{
                        width: 24,
                        height: 24,
                        fontSize: theme => theme.typography.caption.fontSize,
                      }}
                    >
                      {(
                        localSource.user?.name ||
                        localSource.user?.email ||
                        'U'
                      )
                        .charAt(0)
                        .toUpperCase()}
                    </Avatar>
                    <Typography variant="body1" color="text.primary">
                      {localSource.user?.name ||
                        localSource.user?.email ||
                        'Unknown'}
                    </Typography>
                  </Box>
                </InfoRow>

                <InfoRow label="Added on">
                  <Typography variant="body1" color="text.primary">
                    {formatDate(localSource.created_at)}
                  </Typography>
                </InfoRow>
              </Box>
            </>
          )}

          {/* Tags - always visible at bottom */}
          <InfoRow label="Tags">
            <SourceTags
              sessionToken={sessionToken}
              source={localSource}
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
            entityId={localSource.id}
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
