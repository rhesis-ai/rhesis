'use client';

import {
  Box,
  Button,
  TextField,
  Typography,
  Tooltip,
  Chip,
  useTheme,
  Grid,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrowOutlined';
import DownloadIcon from '@mui/icons-material/Download';
import DocumentIcon from '@mui/icons-material/InsertDriveFileOutlined';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { useState } from 'react';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '../../../../../utils/api-client/client-factory';
import ExecuteTestSetDrawer from './ExecuteTestSetDrawer';
import CancelIcon from '@mui/icons-material/CancelOutlined';
import CheckIcon from '@mui/icons-material/CheckOutlined';
import EditIcon from '@mui/icons-material/EditOutlined';
import TestSetTags from './TestSetTags';

interface TestSetDetailsSectionProps {
  testSet: TestSet;
  sessionToken: string;
}

interface MetadataFieldProps {
  label: string;
  items: string[];
  maxVisible?: number;
}

function MetadataField({ label, items, maxVisible = 20 }: MetadataFieldProps) {
  if (!items || items.length === 0) {
    return (
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
          {label}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          No {label.toLowerCase()} defined
        </Typography>
      </Box>
    );
  }

  const visibleItems = items.slice(0, maxVisible);
  const remainingCount = items.length - maxVisible;

  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
        {label}
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {visibleItems.map((item, index) => (
          <Chip key={index} label={item} variant="outlined" size="small" />
        ))}
        {remainingCount > 0 && (
          <Chip
            label={`+${remainingCount}`}
            variant="outlined"
            size="small"
            sx={{
              fontWeight: 'medium',
            }}
          />
        )}
      </Box>
    </Box>
  );
}

export default function TestSetDetailsSection({
  testSet,
  sessionToken,
}: TestSetDetailsSectionProps) {
  const theme = useTheme();
  const [testRunDrawerOpen, setTestRunDrawerOpen] = useState(false);
  const [isEditingDescription, setIsEditingDescription] = useState(false);
  const [editedDescription, setEditedDescription] = useState(
    testSet.description || ''
  );
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState(testSet.name || '');
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const { data: session } = useSession();

  if (!session) {
    return null;
  }

  const handleEditDescription = () => {
    setIsEditingDescription(true);
  };

  const handleEditTitle = () => {
    setIsEditingTitle(true);
  };

  const handleCancelEdit = () => {
    setIsEditingDescription(false);
    setEditedDescription(testSet.description || '');
  };

  const handleCancelTitleEdit = () => {
    setIsEditingTitle(false);
    setEditedTitle(testSet.name || '');
  };

  const handleConfirmEdit = async () => {
    if (!sessionToken) return;

    setIsUpdating(true);
    try {
      const clientFactory: ApiClientFactory = new ApiClientFactory(
        sessionToken
      );
      const testSetsClient = clientFactory.getTestSetsClient();

      await testSetsClient.updateTestSet(testSet.id, {
        description: editedDescription,
      });

      // Update the testSet object to reflect the new description
      testSet.description = editedDescription;
      setIsEditingDescription(false);
    } catch (error) {
      // Reset the edited description to the original value on error
      setEditedDescription(testSet.description || '');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleConfirmTitleEdit = async () => {
    if (!sessionToken) return;

    setIsUpdating(true);
    try {
      const clientFactory: ApiClientFactory = new ApiClientFactory(
        sessionToken
      );
      const testSetsClient = clientFactory.getTestSetsClient();

      await testSetsClient.updateTestSet(testSet.id, {
        name: editedTitle,
      });

      // Update the testSet object to reflect the new title
      testSet.name = editedTitle;
      setIsEditingTitle(false);

      // Refresh the page to update breadcrumbs and title
      window.location.reload();
    } catch (error) {
      // Reset the edited title to the original value on error
      setEditedTitle(testSet.name || '');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDownloadTestSet = async () => {
    if (!sessionToken) return;

    setIsDownloading(true);
    try {
      const clientFactory: ApiClientFactory = new ApiClientFactory(
        sessionToken
      );
      const testSetsClient = clientFactory.getTestSetsClient();

      const blob = await testSetsClient.downloadTestSet(testSet.id);

      // Create a download link and trigger the download
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `test_set_${testSet.id}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      // You might want to show a user-friendly error message here
    } finally {
      setIsDownloading(false);
    }
  };

  // Extract metadata from testSet
  const behaviors = testSet.attributes?.metadata?.behaviors || [];
  const categories = testSet.attributes?.metadata?.categories || [];
  const topics = testSet.attributes?.metadata?.topics || [];
  const sources = testSet.attributes?.metadata?.sources || [];
  const totalTests = testSet.attributes?.metadata?.total_tests || 0;

  return (
    <>
      {/* Action Buttons */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }} suppressHydrationWarning>
        <Tooltip
          title={
            totalTests === 0 ? 'Cannot execute a test set with 0 tests' : ''
          }
          arrow
        >
          <span>
            <Button
              variant="contained"
              color="primary"
              startIcon={<PlayArrowIcon />}
              onClick={() => setTestRunDrawerOpen(true)}
              disabled={totalTests === 0}
            >
              Execute Test Set
            </Button>
          </span>
        </Tooltip>
        <Button
          variant="outlined"
          startIcon={<DownloadIcon />}
          onClick={handleDownloadTestSet}
          disabled={isDownloading}
        >
          {isDownloading ? 'Downloading...' : 'Download Test Set'}
        </Button>
      </Box>

      {/* Test Set Details */}
      <Box sx={{ mb: 3, position: 'relative' }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Test Set Details
        </Typography>

        {/* Name Field */}
        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
          Name
        </Typography>
        {isEditingTitle ? (
          <TextField
            fullWidth
            value={editedTitle}
            onChange={e => setEditedTitle(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleConfirmTitleEdit();
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
                color: 'text.primary',
                borderRadius: theme => theme.shape.borderRadius * 0.25,
                padding: 1,
                paddingRight: theme.spacing(10),
                wordBreak: 'break-word',
                minHeight: 'calc(2 * 1.4375em + 2 * 8px)', // Increased height for longer titles
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {editedTitle}
            </Typography>
            <Button
              startIcon={<EditIcon />}
              onClick={handleEditTitle}
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

        {/* Title Edit Actions */}
        {isEditingTitle && (
          <Box
            sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mb: 3 }}
          >
            <Button
              variant="outlined"
              color="error"
              startIcon={<CancelIcon />}
              onClick={handleCancelTitleEdit}
              disabled={isUpdating}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              color="primary"
              startIcon={<CheckIcon />}
              onClick={handleConfirmTitleEdit}
              disabled={isUpdating}
            >
              Confirm
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
            sx={{ mb: 1 }}
            autoFocus
          />
        ) : (
          <Box sx={{ position: 'relative' }}>
            <Typography
              component="pre"
              variant="body2"
              sx={{
                whiteSpace: 'pre-wrap',
                fontFamily: 'monospace',
                bgcolor: 'action.hover',
                color: 'text.primary',
                borderRadius: theme => theme.shape.borderRadius * 0.25,
                padding: 1,
                minHeight: 'calc(4 * 1.4375em + 2 * 8px)',
                paddingRight: theme.spacing(10),
                wordBreak: 'break-word',
              }}
            >
              {testSet.description || ' '}
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
      </Box>

      {isEditingDescription && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
          <Button
            variant="outlined"
            color="error"
            startIcon={<CancelIcon />}
            onClick={handleCancelEdit}
            disabled={isUpdating}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            color="primary"
            startIcon={<CheckIcon />}
            onClick={handleConfirmEdit}
            disabled={isUpdating}
          >
            Confirm
          </Button>
        </Box>
      )}

      {/* Creator Information */}
      <Box sx={{ mb: 4, mt: 3 }}>
        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
          Created by
        </Typography>
        <Typography
          variant="body2"
          sx={{
            bgcolor: 'action.hover',
            borderRadius: theme => theme.shape.borderRadius * 0.25,
            padding: 1,
          }}
        >
          {testSet.user?.name || testSet.user?.email || 'Not available'}
        </Typography>
      </Box>

      {/* Metadata Fields */}
      <Box sx={{ mb: 3 }}>
        <MetadataField label="Behaviors" items={behaviors} />
        <MetadataField label="Categories" items={categories} />
        <MetadataField label="Topics" items={topics} />
      </Box>

      {/* Source Documents Section */}
      {sources.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
            Source Documents
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {sources.map((source: any, index: number) => (
              <Box
                key={index}
                sx={{
                  p: 2,
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: theme => theme.shape.borderRadius * 0.25,
                  backgroundColor: 'background.paper',
                }}
              >
                <Typography
                  variant="subtitle1"
                  sx={{
                    fontWeight: 'bold',
                    mb: 1,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                  }}
                >
                  <DocumentIcon sx={{ fontSize: 'inherit' }} />
                  {source.name || source.document || 'Unknown Document'}
                </Typography>
                {source.description && (
                  <Typography variant="body2" color="text.secondary">
                    {source.description}
                  </Typography>
                )}
                {source.document && source.document !== source.name && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: 'block', mt: 0.5 }}
                  >
                    File: {source.document}
                  </Typography>
                )}
              </Box>
            ))}
          </Box>
        </Box>
      )}

      {/* Tags Section */}
      <TestSetTags sessionToken={sessionToken} testSet={testSet} />

      <ExecuteTestSetDrawer
        open={testRunDrawerOpen}
        onClose={() => setTestRunDrawerOpen(false)}
        testSetId={testSet.id}
        sessionToken={sessionToken}
      />
    </>
  );
}
