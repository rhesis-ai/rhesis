'use client';

import React, { useMemo, useState } from 'react';
import {
  Box,
  Collapse,
  IconButton,
  LinearProgress,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import MarkdownContent from '@/components/common/MarkdownContent';

interface PlanDisplayProps {
  plan: string;
}

function countProgress(plan: string): { done: number; total: number } {
  const lines = plan.split('\n');
  let total = 0;
  let done = 0;
  for (const line of lines) {
    if (line.startsWith('- [x] ') || line.startsWith('- [ ] ')) {
      // Skip existing/reused items — they carry a *(status)* tag and are
      // already present, so they don't belong in the "to-do" count.
      if (/\*\([^)]+\)\*/.test(line)) continue;
      total++;
      if (line.startsWith('- [x] ')) done++;
    }
  }
  return { done, total };
}

export default function PlanDisplay({ plan }: PlanDisplayProps) {
  const [expanded, setExpanded] = useState(false);
  const { done, total } = useMemo(() => countProgress(plan), [plan]);
  const progress = total > 0 ? Math.round((done / total) * 100) : 0;
  const isComplete = total > 0 && done === total;

  return (
    <Box
      sx={{
        mx: 2,
        mb: 1,
        border: 1,
        borderColor: isComplete ? 'success.main' : 'divider',
        borderRadius: theme => theme.shape.borderRadius,
        bgcolor: 'background.paper',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 0.5,
          cursor: 'pointer',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box
          sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1, mr: 1 }}
        >
          {isComplete ? (
            <CheckCircleIcon sx={{ fontSize: 18, color: 'success.main' }} />
          ) : null}
          <Typography
            variant="subtitle2"
            color={isComplete ? 'success.main' : 'text.secondary'}
            sx={{ whiteSpace: 'nowrap' }}
          >
            {isComplete ? 'Plan Complete' : 'Current Plan'}
          </Typography>
          {total > 0 && !isComplete && (
            <>
              <LinearProgress
                variant="determinate"
                value={progress}
                sx={{
                  flex: 1,
                  maxWidth: 120,
                  height: 4,
                  borderRadius: theme => theme.shape.borderRadius * 2,
                }}
              />
              <Typography variant="caption" color="text.secondary">
                {done}/{total}
              </Typography>
            </>
          )}
        </Box>
        <IconButton size="small">
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2, maxHeight: 300, overflow: 'auto' }}>
          <MarkdownContent content={plan} variant="body2" />
        </Box>
      </Collapse>
    </Box>
  );
}
