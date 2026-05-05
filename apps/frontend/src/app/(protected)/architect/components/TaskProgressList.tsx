'use client';

import React from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import { TaskProgressEntry } from '@/hooks/useArchitectChat';

interface TaskProgressListProps {
  entries: TaskProgressEntry[];
  /**
   * True while the parent bubble is still waiting for the background
   * task. The most-recent entry is rendered with a live spinner only
   * while this is true; once the wait ends, all entries flatten to
   * static history (the user can still see them in scroll-back).
   */
  isAwaiting: boolean;
}

function formatDuration(ms?: number): string | null {
  if (ms === undefined || ms === null) return null;
  if (ms < 1000) return `${ms}ms`;
  const secs = ms / 1000;
  if (secs < 60) return `${secs.toFixed(1)}s`;
  const mins = Math.floor(secs / 60);
  const rem = Math.round(secs % 60);
  return `${mins}m ${rem}s`;
}

/**
 * Render the per-step progress trail produced by a background worker
 * (e.g. exploration). Stays visible after completion so the user can
 * scroll back and see what happened during the long-running task.
 */
export default function TaskProgressList({
  entries,
  isAwaiting,
}: TaskProgressListProps) {
  if (!entries.length) return null;

  const lastIdx = entries.length - 1;

  return (
    <Box
      sx={{
        mt: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: 0.5,
        pl: 0.5,
      }}
      aria-label="Task progress"
    >
      {entries.map((entry, idx) => {
        const isLast = idx === lastIdx;
        const isFailed = entry.status === 'failed';
        const isCompleted = entry.status === 'completed';
        // Render a live spinner only on the latest in-progress entry
        // while we're still actively waiting on the worker. Older
        // entries flatten to a muted "done" appearance even if their
        // status is "started"/"progress" (the next entry implicitly
        // marks them completed).
        const showSpinner =
          isAwaiting &&
          isLast &&
          (entry.status === 'started' || entry.status === 'progress');
        const duration = formatDuration(entry.durationMs);

        let icon: React.ReactNode;
        let textColor: string;
        if (showSpinner) {
          icon = (
            <CircularProgress size={10} thickness={5} sx={{ color: 'inherit' }} />
          );
          textColor = 'text.secondary';
        } else if (isFailed) {
          icon = <ErrorOutlineIcon sx={{ fontSize: 12, color: 'error.main' }} />;
          textColor = 'error.main';
        } else if (isCompleted || !isAwaiting || !isLast) {
          icon = (
            <CheckCircleOutlineIcon
              sx={{ fontSize: 12, color: 'success.main', opacity: 0.7 }}
            />
          );
          textColor = 'text.secondary';
        } else {
          icon = (
            <RadioButtonUncheckedIcon
              sx={{ fontSize: 12, color: 'text.disabled' }}
            />
          );
          textColor = 'text.disabled';
        }

        return (
          <Box
            key={`${entry.taskId}-${idx}-${entry.receivedAt}`}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.75,
              minHeight: 16,
            }}
          >
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 12,
                height: 12,
                color: 'text.secondary',
              }}
            >
              {icon}
            </Box>
            <Typography
              variant="caption"
              sx={{ color: textColor, lineHeight: 1.4 }}
            >
              {entry.label}
              {entry.step !== undefined && entry.total !== undefined ? (
                <Typography
                  component="span"
                  variant="caption"
                  sx={{ color: 'text.disabled', ml: 0.5 }}
                >
                  ({entry.step}/{entry.total})
                </Typography>
              ) : entry.step !== undefined ? (
                <Typography
                  component="span"
                  variant="caption"
                  sx={{ color: 'text.disabled', ml: 0.5 }}
                >
                  ({entry.step})
                </Typography>
              ) : null}
              {duration && (
                <Typography
                  component="span"
                  variant="caption"
                  sx={{ color: 'text.disabled', ml: 0.5 }}
                >
                  {duration}
                </Typography>
              )}
            </Typography>
          </Box>
        );
      })}
    </Box>
  );
}
