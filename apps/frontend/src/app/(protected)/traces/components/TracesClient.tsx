'use client';

import { Box, Paper, Typography, Alert } from '@mui/material';

interface TracesClientProps {
  sessionToken: string;
}

/**
 * Main client component for traces view
 *
 * This is a placeholder that will be expanded in WP3
 * to include filters, table, and drawer functionality.
 */
export default function TracesClient({ sessionToken }: TracesClientProps) {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Traces
      </Typography>

      <Alert severity="info" sx={{ mt: 2 }}>
        Trace visualization coming soon. This page will display OpenTelemetry
        traces captured during test executions and endpoint invocations.
      </Alert>

      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="body1" color="text.secondary">
          Features:
        </Typography>
        <ul>
          <li>Filter traces by project, environment, time range, and status</li>
          <li>View trace summaries with duration, span count, and cost</li>
          <li>Drill down into individual traces to see span hierarchies</li>
          <li>Analyze LLM operations, timing, and errors</li>
        </ul>
      </Paper>
    </Box>
  );
}
