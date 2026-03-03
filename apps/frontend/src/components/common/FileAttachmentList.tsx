'use client';

import React, { useEffect, useState } from 'react';
import {
  Box,
  IconButton,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Skeleton,
  Tooltip,
  type Theme,
} from '@mui/material';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import AudioFileIcon from '@mui/icons-material/AudioFile';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import { FileResponse } from '@/utils/api-client/interfaces/file';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

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

/** Renders a single image thumbnail fetched with auth headers. */
function AuthImage({
  fileId,
  filename,
  sessionToken,
}: {
  fileId: string;
  filename: string;
  sessionToken: string;
}) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    const load = async () => {
      try {
        const factory = new ApiClientFactory(sessionToken);
        const client = factory.getFilesClient();
        const blob = await client.getFileContent(fileId);
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      } catch {
        // Silently fail — no thumbnail
      }
    };

    load();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fileId, sessionToken]);

  if (!src) {
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
        borderRadius: 1,
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
    <List dense>
      {files.map(file => {
        const isImage = file.content_type.startsWith('image/');

        return (
          <ListItem
            key={file.id}
            secondaryAction={
              onDelete ? (
                <Tooltip title="Delete file">
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={() => onDelete(file.id)}
                  >
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              ) : undefined
            }
          >
            <ListItemIcon sx={(theme: Theme) => ({ minWidth: theme.spacing(6) })}>
              {isImage ? (
                <AuthImage
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
              primaryTypographyProps={{
                variant: 'body2',
                noWrap: true,
              }}
              secondaryTypographyProps={{ variant: 'caption' }}
            />
          </ListItem>
        );
      })}
    </List>
  );
}
