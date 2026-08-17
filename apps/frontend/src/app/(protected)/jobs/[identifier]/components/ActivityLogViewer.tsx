'use client';

import * as React from 'react';
import {
  Box,
  Button,
  Chip,
  FormControlLabel,
  Paper,
  Switch,
  Typography,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import type { ActivityLogEntry } from '@/utils/api-client/interfaces/job';
import { ACTIVITY_LEVEL_COLOR } from '@/constants/jobs';
import { BORDER_RADIUS } from '@/styles/theme';

interface ActivityLogViewerProps {
  entries: ActivityLogEntry[];
  /** Whether the job is still producing entries. Drives the follow toggle. */
  live: boolean;
  follow: boolean;
  onFollowChange: (follow: boolean) => void;
  onCopy: () => void;
}

const LEVELS = ['info', 'warning', 'error'] as const;

export default function ActivityLogViewer({
  entries,
  live,
  follow,
  onFollowChange,
  onCopy,
}: ActivityLogViewerProps) {
  const [hiddenLevels, setHiddenLevels] = React.useState<Set<string>>(
    () => new Set()
  );
  const scrollRef = React.useRef<HTMLDivElement>(null);

  const visible = React.useMemo(
    () => entries.filter(entry => !hiddenLevels.has(entry.level)),
    [entries, hiddenLevels]
  );

  // Follow the tail only while following is on, so a user who has scrolled up
  // to read something is not yanked back down by the next poll.
  React.useEffect(() => {
    if (!follow) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [visible.length, follow]);

  const toggleLevel = (level: string) => {
    setHiddenLevels(prev => {
      const next = new Set(prev);
      if (next.has(level)) {
        next.delete(level);
      } else {
        next.add(level);
      }
      return next;
    });
  };

  return (
    <Paper variant="outlined" sx={{ borderRadius: BORDER_RADIUS.md }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          flexWrap: 'wrap',
          p: 1.5,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Typography variant="subtitle2" sx={{ mr: 'auto' }}>
          Activity
        </Typography>

        {LEVELS.map(level => (
          <Chip
            key={level}
            size="small"
            label={level}
            color={ACTIVITY_LEVEL_COLOR[level] ?? 'default'}
            variant={hiddenLevels.has(level) ? 'outlined' : 'filled'}
            onClick={() => toggleLevel(level)}
          />
        ))}

        {live && (
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={follow}
                onChange={e => onFollowChange(e.target.checked)}
              />
            }
            label="Follow"
          />
        )}

        <Button size="small" startIcon={<ContentCopyIcon />} onClick={onCopy}>
          Copy
        </Button>
      </Box>

      <Box
        ref={scrollRef}
        sx={{
          maxHeight: 480,
          overflowY: 'auto',
          fontFamily: 'monospace',
          fontSize: 13,
          p: 1.5,
        }}
      >
        {visible.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {entries.length === 0
              ? 'No activity recorded for this job.'
              : 'All entries are hidden by the level filters above.'}
          </Typography>
        ) : (
          visible.map(entry => (
            <Box
              key={entry.id}
              sx={{
                display: 'flex',
                gap: 1.5,
                py: 0.25,
                color:
                  entry.level === 'error'
                    ? 'error.main'
                    : entry.level === 'warning'
                      ? 'warning.main'
                      : 'text.primary',
              }}
            >
              <Box
                component="span"
                sx={{ color: 'text.secondary', flexShrink: 0 }}
              >
                {new Date(entry.created_at).toLocaleTimeString()}
              </Box>
              <Box component="span" sx={{ whiteSpace: 'pre-wrap' }}>
                {entry.message}
              </Box>
            </Box>
          ))
        )}
      </Box>
    </Paper>
  );
}
