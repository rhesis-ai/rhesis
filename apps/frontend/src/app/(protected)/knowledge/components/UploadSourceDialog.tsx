'use client';

import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Alert,
  LinearProgress,
  IconButton,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import UploadIcon from '@mui/icons-material/Upload';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import DragAndDropUpload from '@/components/common/DragAndDropUpload';
import {
  FILE_SIZE_CONSTANTS,
  FILE_TYPE_CONSTANTS,
} from '@/constants/knowledge';

interface UploadSourceDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  sessionToken: string;
}

export default function UploadSourceDialog({
  open,
  onClose,
  onSuccess,
  sessionToken,
}: UploadSourceDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const notifications = useNotifications();

  const handleFileSelect = (file: File) => {
    setFile(file);
    // Auto-populate title with filename if not already set
    if (!title) {
      setTitle(file.name);
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

      // Check if content extraction failed
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

      // Reset form and close dialog
      handleClose();
      onSuccess();
    } catch (error) {
      console.error('Error uploading source:', error);
      const errorMessage =
        error instanceof Error && (error as any).data
          ? JSON.stringify((error as any).data, null, 2)
          : error instanceof Error
            ? error.message
            : 'Failed to upload source. Please try again.';
      setError(errorMessage);
    } finally {
      setUploading(false);
    }
  };

  const handleClose = () => {
    if (!uploading) {
      setFile(null);
      setTitle('');
      setDescription('');
      setError(null);
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: { minHeight: '400px' },
      }}
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box display="flex" alignItems="center" gap={1}>
            <UploadIcon />
            <Typography variant="h6">Upload Source</Typography>
          </Box>
          <IconButton onClick={handleClose} disabled={uploading}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mt: 1 }}>
          {/* File Upload Section */}
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

          {/* Title Field */}
          <TextField
            label="Title"
            value={title}
            onChange={e => setTitle(e.target.value)}
            fullWidth
            required
            disabled={uploading}
            placeholder="Enter a title for this source"
          />

          {/* Description Field */}
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

          {/* Error Display */}
          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}

          {/* Upload Progress */}
          {uploading && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Uploading source...
              </Typography>
              <LinearProgress />
            </Box>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 3, pt: 1 }}>
        <Button onClick={handleClose} disabled={uploading}>
          Cancel
        </Button>
        <Button
          onClick={handleUpload}
          variant={uploading ? 'outlined' : 'contained'}
          disabled={!file || !title.trim() || uploading}
          startIcon={<UploadIcon />}
        >
          {uploading ? 'Uploading...' : 'Upload Source'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
