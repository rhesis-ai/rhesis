'use client';

import React from 'react';
import {
  Box,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Skeleton,
  Tooltip,
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

/**
 * Renders an image thumbnail backed by the TanStack-cached `useFileThumbnail`
 * Blob and a render-scoped object URL that is revoked on unmount / change.
 */
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
        sx={(theme: Theme) => ({
          width: theme.spacing(4.5),
          height: theme.spacing(4.5),
        })}
      />
    );
  }

  return (
    <Box
      component="img"
      src={src}
      alt={filename}
      sx={(theme: Theme) => ({
        width: theme.spacing(4.5),
        height: theme.spacing(4.5),
        objectFit: 'cover',
        borderRadius: `${theme.shape.borderRadius}px`,
      })}
    />
  );
}

function getFileIcon(contentType: string) {
  if (contentType === 'application/pdf')
    return <PictureAsPdfIcon fontSize="small" />;
  if (contentType.startsWith('audio/'))
    return <AudioFileIcon fontSize="small" />;
  return <InsertDriveFileIcon fontSize="small" />;
}

/** Single file row — extracted as a component so hooks can be called unconditionally. */
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
    <ListItem
      disablePadding
      secondaryAction={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {contentUrl && (
            <Tooltip title="Download">
              <IconButton
                edge="end"
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
              <IconButton
                edge="end"
                size="small"
                onClick={() => onDelete(file.id)}
              >
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      }
    >
      <ListItemButton
        dense
        component="a"
        href={contentUrl ?? '#'}
        download={file.filename}
        sx={(theme: Theme) => ({
          borderRadius: `${theme.shape.borderRadius}px`,
        })}
      >
        <ListItemIcon sx={(theme: Theme) => ({ minWidth: theme.spacing(6) })}>
          {isImage ? (
            <ThumbnailImage
              fileId={file.id}
              filename={file.filename}
              sessionToken={sessionToken}
            />
          ) : (
            getFileIcon(file.content_type)
          )}
        </ListItemIcon>
        <ListItemText
          primary={file.filename}
          secondary={formatFileSize(file.size_bytes)}
          primaryTypographyProps={{ variant: 'body2', noWrap: true }}
          secondaryTypographyProps={{ variant: 'caption' }}
        />
      </ListItemButton>
    </ListItem>
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
            sx={(theme: Theme) => ({ height: theme.spacing(6) })}
          />
        ))}
      </Box>
    );
  }

  if (files.length === 0) return null;

  return (
    <List dense disablePadding>
      {files.map(file => (
        <FileRow
          key={file.id}
          file={file}
          sessionToken={sessionToken}
          onDelete={onDelete}
        />
      ))}
    </List>
  );
}
