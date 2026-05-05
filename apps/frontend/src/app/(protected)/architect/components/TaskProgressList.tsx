'use client';

import React, { useState } from 'react';
import {
  Box,
  ButtonBase,
  CircularProgress,
  Collapse,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { TaskProgressEntry } from '@/hooks/useArchitectChat';

interface TaskProgressListProps {
  entries: TaskProgressEntry[];
  /**
   * True while the parent bubble is still waiting for the background
   * task. The most-recent entry is rendered with a live spinner only
   * while this is true; once the wait ends, all entries flatten to
   * static history (the user can still see them in scroll-back until
   * the parent bubble decides to hide the trail entirely).
   */
  isAwaiting: boolean;
}

/**
 * Number of most-recent entries that stay always-visible. Older entries
 * roll into a collapsed "N earlier" summary, mirroring the pattern in
 * ``ToolCallList``. Two is enough to show "previous turn" + "current
 * turn" context without piling up the screen on long explorations.
 */
const VISIBLE_RECENT = 2;

const ENTER_DURATION_MS = 200;
const EXPAND_DURATION_MS = 200;

function formatDuration(ms?: number): string | null {
  if (ms === undefined || ms === null) return null;
  if (ms < 1000) return `${ms}ms`;
  const secs = ms / 1000;
  if (secs < 60) return `${secs.toFixed(1)}s`;
  const mins = Math.floor(secs / 60);
  const rem = Math.round(secs % 60);
  return `${mins}m ${rem}s`;
}

interface EntryRowProps {
  entry: TaskProgressEntry;
  showSpinner: boolean;
}

function EntryRow({ entry, showSpinner }: EntryRowProps) {
  const isFailed = entry.status === 'failed';
  const isCompleted = entry.status === 'completed';
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
  } else if (isCompleted) {
    icon = (
      <CheckCircleOutlineIcon
        sx={{ fontSize: 12, color: 'success.main', opacity: 0.7 }}
      />
    );
    textColor = 'text.secondary';
  } else {
    // started/progress entry that has been superseded by a newer one —
    // implicitly done from the user's perspective.
    icon = (
      <RadioButtonUncheckedIcon
        sx={{ fontSize: 12, color: 'text.disabled' }}
      />
    );
    textColor = 'text.disabled';
  }

  return (
    <Box
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
      <Typography variant="caption" sx={{ color: textColor, lineHeight: 1.4 }}>
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
}

/**
 * Render the per-step progress trail produced by a background worker
 * (e.g. exploration). New entries appear as they stream in, and older
 * completed entries progressively fold into a collapsible "N earlier"
 * summary so a long-running task does not pile up on the screen.
 *
 * The parent bubble decides when to hide the trail entirely (typically
 * once ``message.taskCompleted`` flips to true).
 */
export default function TaskProgressList({
  entries,
  isAwaiting,
}: TaskProgressListProps) {
  const [expandedEarlier, setExpandedEarlier] = useState(false);

  if (!entries.length) return null;

  const lastIdx = entries.length - 1;
  // Only the latest entry can be "live"; older ones are implicitly
  // finished even if their reported status is "started"/"progress",
  // because a newer entry has superseded them.
  const lastEntry = entries[lastIdx];
  const lastIsLive =
    isAwaiting &&
    (lastEntry.status === 'started' || lastEntry.status === 'progress');

  const earlierCount = Math.max(0, entries.length - VISIBLE_RECENT);
  const earlier = earlierCount > 0 ? entries.slice(0, earlierCount) : [];
  const recent =
    earlierCount > 0 ? entries.slice(earlierCount) : entries;

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
      {/* Collapsed summary for older entries. Mirrors the
          "N completed" pattern from ToolCallList. */}
      {earlierCount > 0 && (
        <ButtonBase
          onClick={() => setExpandedEarlier(prev => !prev)}
          aria-label="Toggle earlier task progress entries"
          aria-expanded={expandedEarlier}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            py: 0.125,
            borderRadius: theme =>
              `${(theme.shape.borderRadius as number) / 2}px`,
            '&:hover': { bgcolor: 'action.hover' },
            justifyContent: 'flex-start',
            textAlign: 'left',
          }}
        >
          <CheckCircleOutlineIcon
            sx={{ fontSize: 12, color: 'success.main', opacity: 0.6 }}
          />
          <Typography
            variant="caption"
            sx={{ color: 'text.secondary', lineHeight: 1.4 }}
          >
            {earlierCount} earlier {earlierCount === 1 ? 'turn' : 'turns'}
          </Typography>
          {expandedEarlier ? (
            <ExpandLessIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          ) : (
            <ExpandMoreIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          )}
        </ButtonBase>
      )}

      {/* Earlier entries (expandable). Each renders as a static
          "done" row — they are by definition not the live entry. */}
      <Collapse in={expandedEarlier} timeout={EXPAND_DURATION_MS}>
        <Box
          sx={{
            ml: 1,
            borderLeft: 1,
            borderColor: 'divider',
            pl: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 0.5,
          }}
        >
          {earlier.map((entry, idx) => (
            <EntryRow
              key={`earlier-${entry.taskId}-${idx}-${entry.receivedAt}`}
              entry={entry}
              showSpinner={false}
            />
          ))}
        </Box>
      </Collapse>

      {/* Recent entries — always visible. Each new arrival animates
          in via Collapse/appear, matching ToolCallList. */}
      {recent.map((entry, idx) => {
        const absoluteIdx = earlierCount + idx;
        const isLast = absoluteIdx === lastIdx;
        const showSpinner = isLast && lastIsLive;
        return (
          <Collapse
            key={`recent-${entry.taskId}-${absoluteIdx}-${entry.receivedAt}`}
            in
            timeout={ENTER_DURATION_MS}
            appear
          >
            <EntryRow entry={entry} showSpinner={showSpinner} />
          </Collapse>
        );
      })}
    </Box>
  );
}
