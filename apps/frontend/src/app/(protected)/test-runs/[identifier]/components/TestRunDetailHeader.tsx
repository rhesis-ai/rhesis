'use client';

import React from 'react';
import { Box, Typography, IconButton, Tooltip } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import CompareArrowsOutlinedIcon from '@mui/icons-material/CompareArrowsOutlined';
import RestartAltOutlinedIcon from '@mui/icons-material/RestartAltOutlined';
import { Fab, FabGroup } from '@/components/common/Fab';
import { DownloadIcon } from '@/components/icons';
import { formatDate } from '@/utils/date';
import { getTestRunDisplayTimestamp } from '@/utils/test-run-utils';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

interface TestRunDetailHeaderProps {
  testRun: TestRunDetail;
  onRename: () => void;
  onCompare: () => void;
  onDownload: () => void;
  onRerun: () => void;
  isDownloading?: boolean;
  canRerun?: boolean;
  canCompare?: boolean;
  /** Gate the rename button on server-driven affordances (default true). */
  canRename?: boolean;
}

export default function TestRunDetailHeader({
  testRun,
  onRename,
  onCompare,
  onDownload,
  onRerun,
  isDownloading = false,
  canRerun = true,
  canCompare = true,
  canRename = true,
}: TestRunDetailHeaderProps) {
  const creatorName =
    testRun.user?.name || testRun.user?.email || 'Unknown user';
  const createdOn = formatDate(getTestRunDisplayTimestamp(testRun));

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
          {canRename && (
            <Tooltip title="Rename test run">
              <IconButton size="small" onClick={onRename} aria-label="Rename">
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
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

      <FabGroup>
        <Fab
          icon={<CompareArrowsOutlinedIcon />}
          tooltip={
            canCompare
              ? 'Compare runs'
              : 'No other test runs on this test set to compare against'
          }
          onClick={onCompare}
          disabled={!canCompare}
          aria-label="Compare runs"
        />
        <Fab
          icon={<DownloadIcon />}
          tooltip="Download results"
          onClick={onDownload}
          loading={isDownloading}
          aria-label="Download results"
        />
        <Fab
          icon={<RestartAltOutlinedIcon />}
          tooltip="Re-run test"
          onClick={onRerun}
          disabled={!canRerun}
          aria-label="Re-run test"
        />
      </FabGroup>
    </Box>
  );
}
