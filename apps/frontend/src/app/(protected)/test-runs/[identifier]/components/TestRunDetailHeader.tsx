'use client';

import React from 'react';
import Link from 'next/link';
import { Box, Chip, Typography, IconButton, Tooltip } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import CompareArrowsOutlinedIcon from '@mui/icons-material/CompareArrowsOutlined';
import RestartAltOutlinedIcon from '@mui/icons-material/RestartAltOutlined';
import { Fab, FabGroup } from '@/components/common/Fab';
import { BiotechIcon, DownloadIcon } from '@/components/icons';
import { formatDate } from '@/utils/date';
import { getTestRunDisplayTimestamp } from '@/utils/test-run-utils';
import { experimentHref } from '@/utils/experiment-links';
import { shortVersion } from '@/utils/api-client/interfaces/parameters';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import TestRunSummarizeFab from './TestRunSummarizeFab';
import {
  type RunStatus,
  RUN_STATUS_COLOR,
  RUN_STATUS_LABEL,
  RUN_STATUS_ICON,
} from '@/constants/test-runs';

interface TestRunDetailHeaderProps {
  testRun: TestRunDetail;
  onRename: () => void;
  onCompare: () => void;
  onDownload: () => void;
  onRerun: () => void;
  isDownloading?: boolean;
  canRerun?: boolean;
  /** Tooltip for the re-run FAB (e.g. when disabled because the test set was deleted). */
  rerunTooltip?: string;
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
  rerunTooltip = 'Re-run test',
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
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 0.5 }}>
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
          <RunStatusPill testRun={testRun} />
        </Box>
        <ExperimentLink testRun={testRun} />
      </Box>

      <FabGroup>
        <TestRunSummarizeFab testRun={testRun} />
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
          tooltip={rerunTooltip}
          onClick={onRerun}
          disabled={!canRerun}
          aria-label="Re-run test"
        />
      </FabGroup>
    </Box>
  );
}

function RunStatusPill({ testRun }: { testRun: TestRunDetail }) {
  const backendStatus = (testRun.status?.name?.toLowerCase() ??
    'completed') as RunStatus;
  const status: RunStatus = RUN_STATUS_LABEL[backendStatus]
    ? backendStatus
    : 'completed';
  const Icon = RUN_STATUS_ICON[status];

  return (
    <Chip
      icon={<Icon />}
      label={RUN_STATUS_LABEL[status]}
      color={RUN_STATUS_COLOR[status]}
      size="small"
      sx={{ fontWeight: 600 }}
    />
  );
}

function ExperimentLink({ testRun }: { testRun: TestRunDetail }) {
  if (!testRun.experiment_id) return null;

  const version =
    typeof testRun.attributes?.parameter_version === 'string'
      ? testRun.attributes.parameter_version
      : undefined;
  const experimentName =
    (testRun.attributes?.parameter_experiment_name as string) || 'Experiment';

  return (
    <Link
      href={experimentHref(testRun.experiment_id, version)}
      target="_blank"
      rel="noopener noreferrer"
      style={{ textDecoration: 'none' }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          mt: 1,
          '&:hover': {
            '& .experiment-name': {
              color: 'primary.main',
              textDecoration: 'underline',
            },
          },
        }}
      >
        <BiotechIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        <Typography
          variant="body2"
          className="experiment-name"
          sx={{
            transition: 'color 0.2s',
            color: 'text.secondary',
            fontWeight: 400,
          }}
        >
          {experimentName}
        </Typography>
        {version && (
          <Chip label={shortVersion(version)} size="small" variant="outlined" />
        )}
      </Box>
    </Link>
  );
}
