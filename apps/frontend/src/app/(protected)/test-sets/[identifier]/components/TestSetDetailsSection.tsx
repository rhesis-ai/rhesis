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
import SecurityIcon from '@mui/icons-material/Security';
import RefreshIcon from '@mui/icons-material/Refresh';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { useState } from 'react';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '../../../../../utils/api-client/client-factory';
import ExecuteTestSetDrawer from './ExecuteTestSetDrawer';
import CancelIcon from '@mui/icons-material/CancelOutlined';
import CheckIcon from '@mui/icons-material/CheckOutlined';
import EditIcon from '@mui/icons-material/EditOutlined';
import TestSetTags from './TestSetTags';
import TestSetMetrics from './TestSetMetrics';
import type { GarakSyncPreviewResponse } from '@/utils/api-client/garak-client';
import { formatDate } from '@/utils/date';

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
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncPreview, setSyncPreview] =
    useState<GarakSyncPreviewResponse | null>(null);
  const [syncError, setSyncError] = useState<string>();
  const { data: session } = useSession();

  // Check if this is a Garak-imported test set
  const isGarakTestSet = testSet.attributes?.source === 'garak';
  const garakVersion = testSet.attributes?.garak_version;
  const garakModules = testSet.attributes?.garak_modules || [];
  const lastSyncedAt = testSet.attributes?.last_synced_at;

  if (!session) {
    return null;
  }

  const handleSyncPreview = async () => {
    if (!sessionToken) return;

    try {
      setSyncError(undefined);
      const clientFactory = new ApiClientFactory(sessionToken);
      const garakClient = clientFactory.getGarakClient();
      const preview = await garakClient.previewSync(testSet.id);
      setSyncPreview(preview);
    } catch (error: any) {
      setSyncError(error.message || 'Failed to get sync preview');
    }
  };

  const handleSync = async () => {
    if (!sessionToken) return;

    try {
      setIsSyncing(true);
      setSyncError(undefined);
      const clientFactory = new ApiClientFactory(sessionToken);
      const garakClient = clientFactory.getGarakClient();
      await garakClient.syncTestSet(testSet.id);
      // Refresh the page to show updated data
      window.location.reload();
    } catch (error: any) {
      setSyncError(error.message || 'Failed to sync test set');
    } finally {
      setIsSyncing(false);
    }
  };

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

    const trimmedTitle = editedTitle.trim();

    // Button is disabled if validation fails, but check anyway
    if (!trimmedTitle || trimmedTitle.length < 2) return;

    setIsUpdating(true);
    try {
      const clientFactory: ApiClientFactory = new ApiClientFactory(
        sessionToken
      );
      const testSetsClient = clientFactory.getTestSetsClient();

      await testSetsClient.updateTestSet(testSet.id, {
        name: trimmedTitle,
      });

      // Update the testSet object to reflect the new title
      testSet.name = trimmedTitle;
      setEditedTitle(trimmedTitle);
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
  const testSetType = testSet.test_set_type?.type_value || 'Unknown';
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
        {isGarakTestSet && (
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={syncPreview ? handleSync : handleSyncPreview}
            disabled={isSyncing}
          >
            {isSyncing
              ? 'Syncing...'
              : syncPreview
                ? 'Confirm Sync'
                : 'Sync from Garak'}
          </Button>
        )}
      </Box>

      {/* Garak Import Information */}
      {isGarakTestSet && (
        <Box
          sx={{
            mb: 3,
            p: 2,
            borderRadius: theme => theme.shape.borderRadius * 0.25,
            bgcolor: 'action.hover',
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <SecurityIcon color="primary" fontSize="small" />
            <Typography variant="subtitle1" fontWeight="medium">
              Garak Security Probes
            </Typography>
            {garakVersion && (
              <Chip
                label={`v${garakVersion}`}
                size="small"
                variant="outlined"
              />
            )}
          </Box>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            This test set was imported from Garak probe modules.
          </Typography>
          {garakModules.length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Modules:{' '}
              </Typography>
              {garakModules.map((mod: string) => (
                <Chip
                  key={mod}
                  label={mod}
                  size="small"
                  variant="outlined"
                  sx={{ mr: 0.5, mb: 0.5 }}
                />
              ))}
            </Box>
          )}
          {lastSyncedAt && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mt: 1 }}
            >
              Last synced: {new Date(lastSyncedAt).toLocaleString()}
            </Typography>
          )}
          {syncPreview && (
            <Box
              sx={{
                mt: 2,
                p: 1.5,
                bgcolor: 'background.paper',
                borderRadius: theme => theme.shape.borderRadius * 0.25,
              }}
            >
              <Typography variant="subtitle2" gutterBottom>
                Sync Preview
              </Typography>
              <Typography variant="body2">
                New version: <strong>{syncPreview.new_version}</strong> (from{' '}
                {syncPreview.old_version})
              </Typography>
              <Typography variant="body2">
                To add: <strong>{syncPreview.to_add}</strong> tests
              </Typography>
              <Typography variant="body2">
                To remove: <strong>{syncPreview.to_remove}</strong> tests
              </Typography>
              <Typography variant="body2">
                Unchanged: <strong>{syncPreview.unchanged}</strong> tests
              </Typography>
            </Box>
          )}
          {syncError && (
            <Typography variant="body2" color="error" sx={{ mt: 1 }}>
              {syncError}
            </Typography>
          )}
        </Box>
      )}

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
            disabled={isUpdating}
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
              disabled={
                isUpdating ||
                !editedTitle.trim() ||
                editedTitle.trim().length < 2
              }
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

      {/* Creation Date */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
          Created
        </Typography>
        <Typography
          variant="body2"
          sx={{
            bgcolor: 'action.hover',
            borderRadius: theme => theme.shape.borderRadius * 0.25,
            padding: 1,
          }}
        >
          {testSet.created_at ? formatDate(testSet.created_at) : 'Not available'}
        </Typography>
      </Box>

      {/* Test Set Type */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
          Test Set Type
        </Typography>
        <Chip
          label={testSetType}
          variant="outlined"
          size="medium"
          sx={{ fontWeight: 'medium' }}
        />
      </Box>

      {/* Metadata Fields */}
      <Box sx={{ mb: 3 }}>
        <MetadataField label="Behaviors" items={behaviors} />
        <MetadataField label="Categories" items={categories} />
        <MetadataField label="Topics" items={topics} />
      </Box>

      {/* Applicable Metrics Section */}
      <TestSetMetrics
        testSetId={testSet.id as string}
        sessionToken={sessionToken}
      />

      {/* Sources Section */}
      {sources.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
            Sources
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
                  {source.name || source.document || 'Unknown Source'}
                </Typography>
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
