'use client';

import React, { useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Stack,
  IconButton,
  Button,
  CircularProgress,
  Chip,
  Alert,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DeleteIcon from '@mui/icons-material/Delete';
import DescriptionIcon from '@mui/icons-material/Description';
import { ProcessedDocument } from '@/utils/api-client/interfaces/documents';

interface DocumentUploadProps {
  documents: ProcessedDocument[];
  onUpload: (files: FileList) => void;
  onRemove: (documentId: string) => void;
  maxFileSize?: number; // in bytes
  supportedExtensions?: string[];
}

const DEFAULT_SUPPORTED_EXTENSIONS = [
  '.docx',
  '.pptx',
  '.xlsx',
  '.pdf',
  '.txt',
  '.csv',
  '.json',
  '.xml',
  '.html',
  '.htm',
  '.zip',
  '.epub',
];

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB

/**
 * DocumentUpload Component
 * Handles document upload with drag-and-drop support
 */
export default function DocumentUpload({
  documents,
  onUpload,
  onRemove,
  maxFileSize = MAX_FILE_SIZE,
  supportedExtensions = DEFAULT_SUPPORTED_EXTENSIONS,
}: DocumentUploadProps) {
  const [isDragging, setIsDragging] = React.useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        onUpload(e.dataTransfer.files);
      }
    },
    [onUpload]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        onUpload(e.target.files);
        e.target.value = ''; // Reset input
      }
    },
    [onUpload]
  );

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'error':
        return 'error';
      default:
        return 'info';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'uploading':
        return 'Uploading...';
      case 'extracting':
        return 'Extracting...';
      case 'generating':
        return 'Processing...';
      case 'completed':
        return 'Ready';
      case 'error':
        return 'Failed';
      default:
        return status;
    }
  };

  const hasProcessingDocuments = documents.some(
    doc => doc.status !== 'completed' && doc.status !== 'error'
  );

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Add context documents to improve test generation quality
      </Typography>

      {/* Upload Area */}
      <input
        type="file"
        multiple
        onChange={handleFileSelect}
        style={{ display: 'none' }}
        id="document-upload-input"
        accept={supportedExtensions.join(',')}
      />

      <Paper
        variant="outlined"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        sx={{
          p: 3,
          textAlign: 'center',
          cursor: 'pointer',
          borderStyle: 'dashed',
          borderWidth: 2,
          borderColor: isDragging ? 'primary.main' : 'divider',
          bgcolor: isDragging ? 'primary.lighter' : 'background.paper',
          transition: 'all 0.2s',
          '&:hover': {
            borderColor: 'primary.light',
            bgcolor: 'action.hover',
          },
          mb: 2,
        }}
        onClick={() =>
          document.getElementById('document-upload-input')?.click()
        }
      >
        <UploadFileIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
        <Typography variant="body1" gutterBottom>
          Drag and drop files here, or click to browse
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Supported formats: {supportedExtensions.join(', ')}
          <br />
          Maximum file size: {Math.round(maxFileSize / 1024 / 1024)} MB
        </Typography>
      </Paper>

      {/* Document List */}
      {documents.length > 0 && (
        <Stack spacing={1}>
          {documents.map(doc => (
            <Paper
              key={doc.id}
              variant="outlined"
              sx={{
                p: 1.5,
                display: 'flex',
                alignItems: 'center',
                gap: 2,
              }}
            >
              <DescriptionIcon sx={{ fontSize: 24, color: 'text.secondary' }} />

              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography
                  variant="body2"
                  fontWeight="medium"
                  sx={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {doc.originalName || doc.name}
                </Typography>
                {doc.status === 'completed' && doc.description && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      display: 'block',
                    }}
                  >
                    {doc.description}
                  </Typography>
                )}
              </Box>

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {doc.status !== 'completed' && doc.status !== 'error' && (
                  <CircularProgress size={16} />
                )}
                <Chip
                  label={getStatusLabel(doc.status)}
                  size="small"
                  color={getStatusColor(doc.status)}
                  variant="outlined"
                />
                {doc.status !== 'uploading' && (
                  <IconButton
                    size="small"
                    onClick={() => onRemove(doc.id)}
                    color="error"
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Processing Warning */}
      {hasProcessingDocuments && (
        <Alert severity="info" sx={{ mt: 2 }}>
          Please wait for all documents to finish processing before continuing
        </Alert>
      )}
    </Box>
  );
}
