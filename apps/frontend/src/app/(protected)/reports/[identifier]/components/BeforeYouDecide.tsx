'use client';

import { Alert, AlertTitle, Box } from '@mui/material';
import type { ReportMetrics } from '@/utils/api-client/interfaces/report';

/** The comparison with the previous report, then the caveats; nothing when all is clear. */
export default function BeforeYouDecide({
  metrics,
  isRelease = true,
}: {
  metrics?: ReportMetrics | null;
  isRelease?: boolean;
}) {
  if (!metrics) return null;
  const lines: string[] = [];
  const comparison = metrics.comparison;
  if (comparison) {
    const names = comparison.newly_failing_requirements.slice(0, 4).join(', ');
    let line = `Compared with ${comparison.baseline.title}: ${comparison.newly_failing} tests newly failing${names ? ` (${names})` : ''}, ${comparison.fixed} fixed.`;
    if (comparison.baseline.result_rule !== metrics.result_rule) {
      line += ' The previous report counted results differently.';
    }
    lines.push(line);
  }
  lines.push(...(metrics.warnings ?? []).map(warning => warning.text));
  if (lines.length === 0) return null;
  return (
    <Alert severity="warning" variant="outlined">
      <AlertTitle>
        {isRelease ? 'Before you decide' : 'Read the numbers with care'}
      </AlertTitle>
      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
        {lines.map(line => (
          <li key={line}>{line}</li>
        ))}
      </Box>
    </Alert>
  );
}
