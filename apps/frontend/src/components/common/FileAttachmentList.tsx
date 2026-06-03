'use client';

import React from 'react';
import { BORDER_RADIUS } from '@/styles/theme';
import {
  Box,
  IconButton,
  Skeleton,
  Tooltip,
  Typography,
  type Theme,
} from '@mui/material';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import DownloadIcon from '@mui/icons-material/Download';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import AudioFileIcon from '@mui/icons-material/AudioFile';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import { FileResponse } from '@/utils/api-client/interfaces/file';
import {
  useFileThumbnail,
  useFileContentUrl,
  useThumbnailObjectUrl,
} from '@/hooks/useFileQueries';

interface FileAttachmentListProps {
  files: FileResponse[];
  sessionToken: string;
  isLoading?: boolean;
  onDelete?: (fileId: string) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function ThumbnailImage({
  fileId,
  filename,
  sessionToken,
}: {
  fileId: string;
  filename: string;
  sessionToken: string;
}) {
  const { data: blob, isLoading } = useFileThumbnail(fileId, 144, sessionToken);
  const src = useThumbnailObjectUrl(blob);

  if (isLoading || !src) {
    return (
      <Skeleton
        variant="rounded"
        sx={{ width: 48, height: 48, flexShrink: 0 }}
      />
    );
  }

  return (
    <Box
      component="img"
      src={src}
      alt={filename}
      sx={{
        width: 48,
        height: 48,
        objectFit: 'cover',
        borderRadius: BORDER_RADIUS.sm,
        flexShrink: 0,
      }}
    />
  );
}

function getFileTypeIcon(contentType: string) {
  if (contentType === 'application/pdf')
    return <PictureAsPdfIcon sx={{ fontSize: 32 }} />;
  if (contentType.startsWith('audio/'))
    return <AudioFileIcon sx={{ fontSize: 32 }} />;
  return <InsertDriveFileIcon sx={{ fontSize: 32 }} />;
}

function FileRow({
  file,
  sessionToken,
  onDelete,
}: {
  file: FileResponse;
  sessionToken: string;
  onDelete?: (fileId: string) => void;
}) {
  const isImage = file.content_type.startsWith('image/');
  const contentUrl = useFileContentUrl(file.id);

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        borderTop: (theme: Theme) =>
          `1px solid ${theme.palette.greyscale.border}`,
        overflow: 'hidden',
      }}
    >
      {/* Thumbnail cell: px=16, py=12 */}
      <Box sx={{ px: '16px', py: '12px', flexShrink: 0 }}>
        <Box
          sx={{
            width: 48,
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: (theme: Theme) => theme.palette.greyscale.border,
            borderRadius: BORDER_RADIUS.sm,
            overflow: 'hidden',
          }}
        >
          {isImage ? (
            <ThumbnailImage
              fileId={file.id}
              filename={file.filename}
              sessionToken={sessionToken}
            />
          ) : (
            getFileTypeIcon(file.content_type)
          )}
        </Box>
      </Box>

      {/* Filename cell: p=12, flex-grow */}
      <Box sx={{ flex: '1 0 0', minWidth: 0, p: '12px' }}>
        <Typography
          sx={{
            fontSize: 14,
            lineHeight: '22px',
            color: (theme: Theme) => theme.palette.greyscale.body,
            wordBreak: 'break-word',
          }}
        >
          {file.filename}
        </Typography>
      </Box>

      {/* File size cell: p=12, right-aligned, bold */}
      <Box
        sx={{
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          p: '12px',
        }}
      >
        <Typography
          sx={{
            fontSize: 14,
            fontWeight: 700,
            lineHeight: '22px',
            color: (theme: Theme) => theme.palette.greyscale.body,
            whiteSpace: 'nowrap',
          }}
        >
          {formatFileSize(file.size_bytes)}
        </Typography>
      </Box>

      {/* Actions cell: 80px, p=12 */}
      <Box
        sx={{
          width: 80,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: '10px',
          p: '12px',
        }}
      >
        {contentUrl && (
          <Tooltip title="Download">
            <IconButton
              size="small"
              component="a"
              href={contentUrl}
              download={file.filename}
            >
              <DownloadIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        {onDelete && (
          <Tooltip title="Delete file">
            <IconButton size="small" onClick={() => onDelete(file.id)}>
              <DeleteOutlineIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Box>
    </Box>
  );
}

export default function FileAttachmentList({
  files,
  sessionToken,
  isLoading = false,
  onDelete,
}: FileAttachmentListProps) {
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {[1, 2].map(i => (
          <Skeleton
            key={i}
            variant="rounded"
            sx={(theme: Theme) => ({ height: theme.spacing(7) })}
          />
        ))}
      </Box>
    );
  }

  if (files.length === 0) return null;

  return (
    <Box>
      {files.map(file => (
        <FileRow
          key={file.id}
          file={file}
          sessionToken={sessionToken}
          onDelete={onDelete}
        />
      ))}
    </Box>
  );
}
