'use client';

import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import {
  Box,
  IconButton,
  InputBase,
  Chip,
  CircularProgress,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import CloseIcon from '@mui/icons-material/Close';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';

export interface FileAttachment {
  filename: string;
  content_type: string;
  data: string;
  size: number;
}

export interface Attachments {
  files?: FileAttachment[];
}

const ACCEPTED_FILE_EXTENSIONS = [
  '.pdf',
  '.docx',
  '.pptx',
  '.xlsx',
  '.txt',
  '.md',
  '.csv',
  '.json',
  '.yaml',
  '.yml',
  '.xml',
  '.html',
  '.htm',
  '.py',
  '.js',
  '.ts',
].join(',');

const MAX_FILE_SIZE = 5 * 1024 * 1024;

export interface ArchitectChatInputHandle {
  focus: () => void;
}

interface ArchitectChatInputProps {
  onSend: (message: string, attachments?: Attachments) => void;
  disabled?: boolean;
  isLoading?: boolean;
  isConnected?: boolean;
  sessionToken?: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const ArchitectChatInput = forwardRef<
  ArchitectChatInputHandle,
  ArchitectChatInputProps
>(function ArchitectChatInput(
  {
    onSend,
    disabled = false,
    isLoading = false,
    isConnected = true,
    sessionToken: _sessionToken,
  },
  ref
) {
  const [value, setValue] = useState('');
  const [files, setFiles] = useState<FileAttachment[]>([]);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useImperativeHandle(ref, () => ({
    focus: () => inputRef.current?.focus(),
  }));

  useEffect(() => {
    if (!disabled && isConnected && inputRef.current) {
      inputRef.current.focus();
    }
  }, [disabled, isConnected]);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled || isLoading) return;

    const attachments: Attachments = {};
    if (files.length > 0) attachments.files = files;

    onSend(trimmed, files.length > 0 ? attachments : undefined);
    setValue('');
    setFiles([]);
  }, [value, files, disabled, isLoading, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files;
      if (!selected) return;

      const newFiles: FileAttachment[] = [];
      for (const file of Array.from(selected)) {
        if (file.size > MAX_FILE_SIZE) {
          console.warn(
            `File ${file.name} exceeds ${formatFileSize(MAX_FILE_SIZE)} limit`
          );
          continue;
        }
        let data: string;
        try {
          data = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              const result = reader.result as string;
              if (!result || !result.includes(',')) {
                reject(new Error('Invalid data URL format'));
                return;
              }
              resolve(result.split(',')[1]);
            };
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.onabort = () => reject(new Error('File read aborted'));
            reader.readAsDataURL(file);
          });
        } catch (err) {
          console.error(`Failed to read file ${file.name}:`, err);
          continue;
        }
        newFiles.push({
          filename: file.name,
          content_type: file.type || 'application/octet-stream',
          data,
          size: file.size,
        });
      }

      setFiles(prev => [...prev, ...newFiles]);
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
    []
  );

  const removeFile = useCallback((index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  }, []);

  const inputDisabled = disabled || !isConnected || isLoading;
  const canSend = value.trim().length > 0 && !inputDisabled;

  return (
    <Box
      sx={{
        p: 2,
        borderTop: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      {files.length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
          {files.map((f, fileIdx) => (
            <Chip
              key={`${f.filename}-${f.size}`}
              icon={<InsertDriveFileIcon />}
              label={`${f.filename} (${formatFileSize(f.size)})`}
              size="small"
              variant="outlined"
              onDelete={() => removeFile(fileIdx)}
              deleteIcon={<CloseIcon />}
            />
          ))}
        </Box>
      )}

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <IconButton
          size="small"
          onClick={() => fileInputRef.current?.click()}
          disabled={inputDisabled}
          sx={{ color: 'text.secondary' }}
        >
          <AttachFileIcon fontSize="small" />
        </IconButton>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_FILE_EXTENSIONS}
          style={{ display: 'none' }}
          onChange={handleFileSelect}
        />

        <Box sx={{ flex: 1 }}>
          <InputBase
            inputRef={inputRef}
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={inputDisabled}
            multiline
            fullWidth
            placeholder={
              isConnected
                ? 'Describe what you want to test...'
                : 'Waiting for connection...'
            }
            sx={theme => ({
              fontSize: theme.typography.body2.fontSize,
              fontFamily: theme.typography.fontFamily,
              minHeight: theme.spacing(5),
              '& .MuiInputBase-input': {
                padding: `${theme.spacing(1)} ${theme.spacing(1.5)}`,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: `${theme.shape.borderRadius}px`,
                outline: 'none',
                lineHeight: '1.5',
                color: theme.palette.text.primary,
                backgroundColor: 'transparent',
                overflow: 'auto',
                maxHeight: theme.spacing(16),
                '&:focus': {
                  borderColor: theme.palette.primary.main,
                  outline: `1px solid ${theme.palette.primary.main}`,
                },
              },
            })}
          />
        </Box>

        <IconButton
          color="primary"
          onClick={handleSend}
          disabled={!canSend}
          sx={{
            width: theme => theme.spacing(5),
            height: theme => theme.spacing(5),
            bgcolor: 'primary.main',
            color: 'primary.contrastText',
            '&:hover': { bgcolor: 'primary.dark' },
            '&:disabled': {
              bgcolor: 'action.disabledBackground',
              color: 'action.disabled',
            },
          }}
        >
          {isLoading ? (
            <CircularProgress size={20} color="inherit" />
          ) : (
            <SendIcon />
          )}
        </IconButton>
      </Box>
    </Box>
  );
});

export default ArchitectChatInput;
