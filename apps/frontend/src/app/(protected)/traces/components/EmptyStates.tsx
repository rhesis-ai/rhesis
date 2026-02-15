'use client';

import { Typography, Paper } from '@mui/material';
import SearchOffIcon from '@mui/icons-material/SearchOff';

/**
 * Empty state component displayed when no traces are found
 */
export function NoTracesFound() {
  return (
    <Paper
      sx={{
        p: 4,
        textAlign: 'center',
        backgroundColor: 'background.default',
      }}
    >
      <SearchOffIcon sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
      <Typography variant="h6" gutterBottom>
        No traces found
      </Typography>
      <Typography variant="body2" color="text.secondary">
        No traces available yet. Try adjusting your filters or check back later
        after running some tests.
      </Typography>
    </Paper>
  );
}
