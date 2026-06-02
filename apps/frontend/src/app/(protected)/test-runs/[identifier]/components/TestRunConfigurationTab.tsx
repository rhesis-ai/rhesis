'use client';

import React from 'react';
import {
  Box,
  Grid,
  Chip,
  Switch,
  FormControlLabel,
  Typography,
} from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import ViewField from '@/components/common/ViewField';
import {
  getMetricsSourceLabel,
  type ExecutionMetric,
} from '@/utils/api-client/interfaces/test-configuration';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import TestRunTags from './TestRunTags';

interface TestRunConfigurationTabProps {
  testRun: TestRunDetail;
  sessionToken: string;
}

export default function TestRunConfigurationTab({
  testRun,
  sessionToken,
}: TestRunConfigurationTabProps) {
  const config = testRun.test_configuration;
  const attrs = config?.attributes as Record<string, unknown> | undefined;
  const execMetrics = (attrs?.metrics as ExecutionMetric[] | undefined) ?? [];
  const metricsSource = attrs?.metrics_source as string | undefined;
  const executionMode = attrs?.execution_mode as string | undefined;
  const scoringTarget =
    (attrs?.is_rescore as boolean | undefined) === true
      ? 'Reuse Outputs'
      : 'Fresh Outputs';
  const evaluationModel =
    (attrs?.evaluation_model_name as string | undefined) ||
    (attrs?.evaluation_model_id as string | undefined) ||
    'Default Model';
  const preflightEnabled =
    (attrs?.run_preflight_checks as boolean | undefined) ?? true;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <SectionCard title="Execution Target">
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <ViewField label="Test Set" value={config?.test_set?.name ?? '—'} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <ViewField
              label="Project"
              value={config?.endpoint?.project?.name ?? '—'}
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <ViewField label="Endpoint" value={config?.endpoint?.name ?? '—'} />
          </Grid>
        </Grid>
      </SectionCard>

      <SectionCard title="Configuration Options">
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <ViewField label="Execution Mode" value={executionMode ?? '—'} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <ViewField label="Scoring Target" value={scoringTarget} />
          </Grid>
        </Grid>
      </SectionCard>

      <SectionCard title="Test Run Metrics">
        <ViewField
          label="Metric Source"
          value={metricsSource ? getMetricsSourceLabel(metricsSource) : '—'}
        />
        {execMetrics.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography
              variant="body2"
              sx={{
                fontSize: 14,
                color: theme => theme.palette.greyscale.subtitle,
                px: '14px',
                mb: '6px',
              }}
            >
              Metrics
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, px: '14px' }}>
              {execMetrics.map(m => (
                <Chip
                  key={m.id}
                  label={m.name}
                  size="small"
                  variant="outlined"
                />
              ))}
            </Box>
          </Box>
        )}
      </SectionCard>

      <SectionCard title="Model Settings">
        <Grid container spacing={3}>
          <Grid size={{ xs: 12 }}>
            <ViewField label="Evaluation Model" value={evaluationModel} />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <FormControlLabel
              control={<Switch checked={preflightEnabled} disabled />}
              label="Run Preflight Checks"
            />
          </Grid>
        </Grid>
      </SectionCard>

      <SectionCard title="Test Run Tags">
        <TestRunTags sessionToken={sessionToken} testRun={testRun} />
      </SectionCard>
    </Box>
  );
}
