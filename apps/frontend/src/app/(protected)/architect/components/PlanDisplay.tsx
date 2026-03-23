'use client';

import React, { useState } from 'react';
import { Box, Collapse, IconButton, Typography } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import MarkdownContent from '@/components/common/MarkdownContent';

interface PlanDisplayProps {
  plan: string;
}

export default function PlanDisplay({ plan }: PlanDisplayProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Box
      sx={{
        mx: 2,
        mb: 1,
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
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
        <Typography variant="subtitle2" color="text.secondary">
          Current Plan
        </Typography>
        <IconButton size="small">
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2, maxHeight: 300, overflow: 'auto' }}>
          <MarkdownContent content={plan} />
        </Box>
      </Collapse>
    </Box>
  );
}
