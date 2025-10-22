'use client';

import React, { useState, useRef } from 'react';
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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const notifications = useNotifications();

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      // Auto-populate title with filename if not already set
      if (!title) {
        setTitle(selectedFile.name);
      }
      setError(null);
    }
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

      await sourcesClient.uploadSource(
        file,
        title.trim(),
        description.trim() || undefined
      );

      notifications.show('Source uploaded successfully!', {
        severity: 'success',
        autoHideDuration: 4000,
      });

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
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      onClose();
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileSelect}
              accept=".txt,.md,.pdf,.doc,.docx,.json,.csv,.xml"
              style={{ display: 'none' }}
            />
            <Button
              variant="outlined"
              component="label"
              startIcon={<UploadIcon />}
              disabled={uploading}
              sx={{ width: '100%', py: 2 }}
            >
              {file ? file.name : 'Choose File'}
              <input
                type="file"
                onChange={handleFileSelect}
                accept=".txt,.md,.pdf,.doc,.docx,.json,.csv,.xml"
                style={{ display: 'none' }}
              />
            </Button>
            {file && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mt: 1, display: 'block' }}
              >
                Size: {formatFileSize(file.size)}
              </Typography>
            )}
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
