'use client';

import React, { useState, useRef, useCallback } from 'react';
import { Box, Typography, Paper, IconButton, Alert } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CloseIcon from '@mui/icons-material/Close';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';

interface DragAndDropUploadProps {
  onFileSelect: (file: File) => void;
  onFileRemove?: () => void;
  selectedFile?: File | null;
  accept?: string;
  maxSize?: number;
  disabled?: boolean;
}

export default function DragAndDropUpload({
  onFileSelect,
  onFileRemove,
  selectedFile,
  accept = '.txt,.md,.pdf,.docx,.json,.csv,.xml,.epub,.pptx,.xlsx,.html,.htm,.zip',
  maxSize = 5 * 1024 * 1024,
  disabled = false,
}: DragAndDropUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const validateFile = (file: File): string | null => {
    if (file.size > maxSize) {
      return `File size exceeds maximum allowed size (${formatFileSize(maxSize)})`;
    }
    const acceptedTypes = accept.split(',').map(type => type.trim());
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!acceptedTypes.includes(fileExtension)) {
      return `File type ${fileExtension} is not supported`;
    }
    return null;
  };

  const handleFile = useCallback(
    (file: File) => {
      console.log('DragAndDropUpload: File selected:', file.name, file.size);
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
      setError(null);
      onFileSelect(file);
    },
    [onFileSelect, maxSize, accept]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled) setIsDragOver(true);
    },
    [disabled]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (disabled) return;
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) handleFile(files[0]);
    },
    [disabled, handleFile]
  );

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) handleFile(files[0]);
  };

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleRemoveFile = () => {
    setError(null);
    if (onFileRemove) onFileRemove();
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <Box>
      <input
        ref={fileInputRef}
        type="file"
        onChange={handleFileInputChange}
        accept={accept}
        style={{ display: 'none' }}
        disabled={disabled}
      />

      <Paper
        elevation={0}
        sx={{
          border: '2px dashed',
          borderColor: 'divider',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.6 : 1,
          p: 3,
          textAlign: 'center',
          minHeight: '100px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          gap: 2,
        }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        component="div"
      >
        {selectedFile ? (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              width: '100%',
            }}
          >
            <InsertDriveFileIcon sx={{ fontSize: 24 }} />
            <Box sx={{ flex: 1, textAlign: 'left' }}>
              <Typography variant="body1">{selectedFile.name}</Typography>
              <Typography variant="caption" color="text.secondary">
                {formatFileSize(selectedFile.size)}
              </Typography>
            </Box>
            <IconButton
              onClick={e => {
                e.stopPropagation();
                handleRemoveFile();
              }}
              size="small"
            >
              <CloseIcon />
            </IconButton>
          </Box>
        ) : (
          <>
            <CloudUploadIcon sx={{ fontSize: 32, color: 'text.secondary' }} />
            <Typography variant="body1">
              {isDragOver ? 'Drop file here' : 'Drag & drop or click to browse'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Max size: {formatFileSize(maxSize)}
            </Typography>
          </>
        )}
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}
    </Box>
  );
}
