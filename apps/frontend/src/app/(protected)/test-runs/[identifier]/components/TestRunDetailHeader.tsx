'use client';

import React from 'react';
import {
  Box,
  Typography,
  IconButton,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import DownloadIcon from '@mui/icons-material/Download';
import ReplayIcon from '@mui/icons-material/Replay';
import { formatDate } from '@/utils/date';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

interface TestRunDetailHeaderProps {
  testRun: TestRunDetail;
  onRename: () => void;
  onCompare: () => void;
  onDownload: () => void;
  onRerun: () => void;
  isDownloading?: boolean;
  canRerun?: boolean;
}

function CircularActionButton({
  title,
  onClick,
  disabled,
  children,
}: {
  title: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Tooltip title={title}>
      <span>
        <IconButton
          onClick={onClick}
          disabled={disabled}
          aria-label={title}
          sx={{
            width: 40,
            height: 40,
            bgcolor: 'primary.main',
            color: 'primary.contrastText',
            '&:hover': {
              bgcolor: 'primary.dark',
            },
            '&.Mui-disabled': {
              bgcolor: theme => theme.palette.action.disabledBackground,
              color: theme => theme.palette.action.disabled,
            },
          }}
        >
          {children}
        </IconButton>
      </span>
    </Tooltip>
  );
}

export default function TestRunDetailHeader({
  testRun,
  onRename,
  onCompare,
  onDownload,
  onRerun,
  isDownloading = false,
  canRerun = true,
}: TestRunDetailHeaderProps) {
  const creatorName =
    testRun.user?.name || testRun.user?.email || 'Unknown user';
  const createdOn = formatDate(testRun.created_at);

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 2,
        mb: 3,
        flexWrap: 'wrap',
      }}
    >
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography
            variant="h4"
            component="h1"
            sx={{
              fontWeight: 700,
              color: theme => theme.palette.greyscale.title,
            }}
          >
            {testRun.name || 'Test Run'}
          </Typography>
          <Tooltip title="Rename test run">
            <IconButton size="small" onClick={onRename} aria-label="Rename">
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        <Typography
          variant="body2"
          sx={{ color: theme => theme.palette.greyscale.subtitle }}
        >
          created by: {creatorName}
          <Box component="span" sx={{ mx: 2 }}>
            |
          </Box>
          created on: {createdOn}
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <CircularActionButton title="Compare runs" onClick={onCompare}>
          <CompareArrowsIcon fontSize="small" />
        </CircularActionButton>
        <CircularActionButton
          title="Download results"
          onClick={onDownload}
          disabled={isDownloading}
        >
          {isDownloading ? (
            <CircularProgress size={20} color="inherit" />
          ) : (
            <DownloadIcon fontSize="small" />
          )}
        </CircularActionButton>
        <CircularActionButton
          title="Re-run test"
          onClick={onRerun}
          disabled={!canRerun}
        >
          <ReplayIcon fontSize="small" />
        </CircularActionButton>
      </Box>
    </Box>
  );
}
