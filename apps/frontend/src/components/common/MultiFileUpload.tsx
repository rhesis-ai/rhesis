'use client';

import React, { useState, useRef, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  IconButton,
  Alert,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  type Theme,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CloseIcon from '@mui/icons-material/Close';
import ImageIcon from '@mui/icons-material/Image';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import AudioFileIcon from '@mui/icons-material/AudioFile';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';

const ACCEPTED_MIME = 'image/*,application/pdf,audio/*';

interface MultiFileUploadProps {
  selectedFiles: File[];
  onFilesSelect: (files: File[]) => void;
  onFileRemove: (index: number) => void;
  maxFileSize?: number;
  maxTotalSize?: number;
  maxFiles?: number;
  existingFilesSize?: number;
  disabled?: boolean;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function getFileIcon(contentType: string) {
  if (contentType.startsWith('image/')) return <ImageIcon fontSize="small" />;
  if (contentType === 'application/pdf')
    return <PictureAsPdfIcon fontSize="small" />;
  if (contentType.startsWith('audio/'))
    return <AudioFileIcon fontSize="small" />;
  return <InsertDriveFileIcon fontSize="small" />;
}

function isAcceptedType(file: File): boolean {
  const type = file.type;
  return (
    type.startsWith('image/') ||
    type === 'application/pdf' ||
    type.startsWith('audio/')
  );
}

export default function MultiFileUpload({
  selectedFiles,
  onFilesSelect,
  onFileRemove,
  maxFileSize = 10 * 1024 * 1024,
  maxTotalSize = 20 * 1024 * 1024,
  maxFiles = 10,
  existingFilesSize = 0,
  disabled = false,
}: MultiFileUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentStagedSize = selectedFiles.reduce((s, f) => s + f.size, 0);

  const validateFiles = useCallback(
    (incoming: File[]): { valid: File[]; errorMsg: string | null } => {
      const totalCount = selectedFiles.length + incoming.length;
      if (totalCount > maxFiles) {
        return {
          valid: [],
          errorMsg: `Maximum ${maxFiles} files allowed`,
        };
      }

      const rejected: string[] = [];
      const accepted: File[] = [];
      let addedSize = 0;

      for (const file of incoming) {
        if (!isAcceptedType(file)) {
          rejected.push(
            `${file.name}: unsupported type (only images, PDFs, and audio)`
          );
          continue;
        }
        if (file.size > maxFileSize) {
          rejected.push(
            `${file.name}: exceeds ${formatFileSize(maxFileSize)} limit`
          );
          continue;
        }
        const runningTotal =
          existingFilesSize + currentStagedSize + addedSize + file.size;
        if (runningTotal > maxTotalSize) {
          rejected.push(
            `${file.name}: would exceed ${formatFileSize(maxTotalSize)} total limit`
          );
          continue;
        }
        addedSize += file.size;
        accepted.push(file);
      }

      const errorMsg = rejected.length > 0 ? rejected.join('. ') : null;
      return { valid: accepted, errorMsg };
    },
    [
      selectedFiles,
      maxFiles,
      maxFileSize,
      maxTotalSize,
      existingFilesSize,
      currentStagedSize,
    ]
  );

  const handleIncoming = useCallback(
    (incoming: File[]) => {
      const { valid, errorMsg } = validateFiles(incoming);
      setError(errorMsg);
      if (valid.length > 0) {
        onFilesSelect(valid);
      }
    },
    [validateFiles, onFilesSelect]
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
      handleIncoming(Array.from(e.dataTransfer.files));
    },
    [disabled, handleIncoming]
  );

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleIncoming(Array.from(e.target.files));
    }
    // Reset so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <Box>
      <Box
        component="input"
        ref={fileInputRef}
        type="file"
        multiple
        onChange={handleFileInputChange}
        accept={ACCEPTED_MIME}
        sx={{ display: 'none' }}
        disabled={disabled}
      />

      <Paper
        elevation={0}
        sx={(theme: Theme) => ({
          border: `2px dashed ${isDragOver ? theme.palette.primary.main : theme.palette.divider}`,
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.6 : 1,
          p: 2,
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 1,
        })}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        component="div"
      >
        <CloudUploadIcon
          sx={(theme: Theme) => ({
            fontSize: theme.spacing(3.5),
            color: theme.palette.text.secondary,
          })}
        />
        <Typography variant="body2">
          {isDragOver
            ? 'Drop files here'
            : 'Drag & drop or click to attach files'}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Images, PDFs, or audio. Max {formatFileSize(maxFileSize)} per file.
        </Typography>
      </Paper>

      {selectedFiles.length > 0 && (
        <List dense sx={{ mt: 1 }}>
          {selectedFiles.map((file, idx) => (
            <ListItem
              key={`${file.name}-${idx}`}
              secondaryAction={
                <IconButton
                  edge="end"
                  size="small"
                  onClick={() => onFileRemove(idx)}
                  disabled={disabled}
                >
                  <CloseIcon fontSize="small" />
                </IconButton>
              }
            >
              <ListItemIcon
                sx={(theme: Theme) => ({ minWidth: theme.spacing(4.5) })}
              >
                {getFileIcon(file.type)}
              </ListItemIcon>
              <ListItemText
                primary={file.name}
                secondary={formatFileSize(file.size)}
                primaryTypographyProps={{ variant: 'body2', noWrap: true }}
                secondaryTypographyProps={{ variant: 'caption' }}
              />
            </ListItem>
          ))}
        </List>
      )}

      {error && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {error}
        </Alert>
      )}
    </Box>
  );
}
