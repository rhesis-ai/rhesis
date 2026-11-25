'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';

/** A labelled value in the job's summary card. */
export default function JobField({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography variant="body2" component="div">
        {value}
      </Typography>
    </Box>
  );
}
