'use client';

import React, { useState, useEffect } from 'react';
import {
  TextField,
  Box,
  Typography,
  Alert,
  LinearProgress,
} from '@mui/material';
import UploadIcon from '@mui/icons-material/Upload';
import BaseDrawer from '@/components/common/BaseDrawer';
import { drawerOutlinedFieldSx } from '@/components/common/drawerFormFieldSx';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import DragAndDropUpload from '@/components/common/DragAndDropUpload';
import {
  FILE_SIZE_CONSTANTS,
  FILE_TYPE_CONSTANTS,
  formatFileSize,
} from '@/constants/knowledge';

interface UploadSourceDrawerProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  sessionToken: string;
}

export default function UploadSourceDrawer({
  open,
  onClose,
  onSuccess,
  sessionToken,
}: UploadSourceDrawerProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const notifications = useNotifications();

  useEffect(() => {
    if (!open) {
      setFile(null);
      setTitle('');
      setDescription('');
      setError(null);
    }
  }, [open]);

  const handleFileSelect = (selected: File) => {
    setFile(selected);
    if (!title) {
      setTitle(selected.name);
    }
    setError(null);
  };

  const handleFileRemove = () => {
    setFile(null);
    setTitle('');
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file to upload');
      return;
    }

    if (!title.trim()) {
      setError('Please enter a title for the source');
      return;
    }

    try {
      setUploading(true);
      setError(null);

      const clientFactory = new ApiClientFactory(sessionToken);
      const sourcesClient = clientFactory.getSourcesClient();

      const uploadedSource = await sourcesClient.uploadSource(
        file,
        title.trim(),
        description.trim() || undefined
      );

      if (!uploadedSource.content || uploadedSource.content.trim() === '') {
        notifications.show(
          'Source uploaded successfully, but content extraction failed. The file may not be supported or corrupted.',
          {
            severity: 'warning',
            autoHideDuration: 8000,
          }
        );
      } else {
        notifications.show('Source uploaded successfully!', {
          severity: 'success',
          autoHideDuration: 4000,
        });
      }

      onClose();
      onSuccess?.();
    } catch (err) {
      const errorMessage =
        err instanceof Error &&
        (err as Error & { data?: Record<string, unknown> }).data
          ? JSON.stringify(
              (err as Error & { data?: Record<string, unknown> }).data,
              null,
              2
            )
          : err instanceof Error
            ? err.message
            : 'Failed to upload source. Please try again.';
      setError(errorMessage);
    } finally {
      setUploading(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Upload Source"
      titleIcon={<UploadIcon color="primary" />}
      loading={uploading}
      onSave={handleUpload}
      saveDisabled={!file || !title.trim()}
      saveButtonText={uploading ? 'Uploading...' : 'Upload Source'}
      error={error ?? undefined}
    >
      <Alert severity="info">
        <Typography variant="body2" color="text.secondary">
          Supported formats:{' '}
          <Typography
            component="span"
            variant="body2"
            sx={{ fontStyle: 'italic' }}
          >
            {FILE_TYPE_CONSTANTS.ACCEPTED_EXTENSIONS.split(',')
              .map(ext => ext.replace('.', ''))
              .join(', ')}
          </Typography>{' '}
          (max {formatFileSize(FILE_SIZE_CONSTANTS.MAX_UPLOAD_SIZE)})
        </Typography>
      </Alert>

      <Box>
        <Typography variant="subtitle2" gutterBottom>
          Select File
        </Typography>
        <DragAndDropUpload
          onFileSelect={handleFileSelect}
          onFileRemove={handleFileRemove}
          selectedFile={file}
          accept={FILE_TYPE_CONSTANTS.ACCEPTED_EXTENSIONS}
          maxSize={FILE_SIZE_CONSTANTS.MAX_UPLOAD_SIZE}
          disabled={uploading}
        />
      </Box>

      <TextField
        label="Title"
        value={title}
        onChange={e => setTitle(e.target.value)}
        fullWidth
        required
        disabled={uploading}
        placeholder="Enter a title for this source"
        sx={drawerOutlinedFieldSx}
      />

      <TextField
        label="Description"
        value={description}
        onChange={e => setDescription(e.target.value)}
        fullWidth
        multiline
        rows={3}
        disabled={uploading}
        placeholder="Optional description of this source"
      />

      {uploading && (
        <Box>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Uploading source...
          </Typography>
          <LinearProgress />
        </Box>
      )}
    </BaseDrawer>
  );
}
