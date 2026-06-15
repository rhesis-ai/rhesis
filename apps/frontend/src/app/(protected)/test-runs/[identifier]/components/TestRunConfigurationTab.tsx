'use client';

import React from 'react';
import { Box, Chip, Grid, Paper, Switch, Typography } from '@mui/material';
import type { Theme } from '@mui/material/styles';
import Link from 'next/link';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import ViewField from '@/components/common/ViewField';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import {
  getMetricsSourceLabel,
  type ExecutionMetric,
} from '@/utils/api-client/interfaces/test-configuration';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

interface TestRunConfigurationTabProps {
  testRun: TestRunDetail;
}

const combinedCardSx = {
  p: '30px',
  borderRadius: BORDER_RADIUS.md,
  boxShadow: (theme: Theme) =>
    theme.palette.mode === 'light' ? ELEVATION.xs : 'none',
  bgcolor: (theme: Theme) =>
    theme.palette.mode === 'light'
      ? '#ffffff'
      : theme.palette.greyscale.surface1,
  border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
  display: 'flex',
  flexDirection: 'column',
  gap: '50px',
} as const;

const sectionSx = {
  display: 'flex',
  flexDirection: 'column',
  gap: '20px',
} as const;

const fieldsSx = {
  display: 'flex',
  flexDirection: 'column',
  gap: '30px',
  width: '100%',
} as const;

export default function TestRunConfigurationTab({
  testRun,
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
    <Paper elevation={0} sx={combinedCardSx}>
      <Box sx={sectionSx}>
        <FormSectionDivider headline="Execution Target" />
        <Box sx={fieldsSx}>
          <Grid container spacing="30px">
            <Grid size={{ xs: 12, sm: 6 }}>
              {config?.test_set?.id ? (
                <ViewField label="Test Set">
                  <Link
                    href={`/test-sets/${config.test_set.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ textDecoration: 'none' }}
                  >
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                        '&:hover .field-link-text': {
                          color: 'primary.main',
                          textDecoration: 'underline',
                        },
                      }}
                    >
                      <Typography
                        className="field-link-text"
                        sx={{
                          fontSize: 16,
                          lineHeight: '24px',
                          color: theme => theme.palette.greyscale.body,
                          transition: 'color 0.2s',
                        }}
                      >
                        {config.test_set.name || '—'}
                      </Typography>
                      <OpenInNewIcon
                        sx={{ fontSize: 14, color: 'text.disabled' }}
                      />
                    </Box>
                  </Link>
                </ViewField>
              ) : (
                <ViewField label="Test Set" value={config?.test_set?.name} />
              )}
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <ViewField
                label="Project"
                value={config?.endpoint?.project?.name}
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              {config?.endpoint?.id ? (
                <ViewField label="Endpoint">
                  <Link
                    href={`/endpoints/${config.endpoint.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ textDecoration: 'none' }}
                  >
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                        '&:hover .field-link-text': {
                          color: 'primary.main',
                          textDecoration: 'underline',
                        },
                      }}
                    >
                      <Typography
                        className="field-link-text"
                        sx={{
                          fontSize: 16,
                          lineHeight: '24px',
                          color: theme => theme.palette.greyscale.body,
                          transition: 'color 0.2s',
                        }}
                      >
                        {config.endpoint.name || '—'}
                      </Typography>
                      <OpenInNewIcon
                        sx={{ fontSize: 14, color: 'text.disabled' }}
                      />
                    </Box>
                  </Link>
                </ViewField>
              ) : (
                <ViewField label="Endpoint" value={config?.endpoint?.name} />
              )}
            </Grid>
          </Grid>
        </Box>
      </Box>

      <Box sx={sectionSx}>
        <FormSectionDivider headline="Configuration Options" />
        <Box sx={fieldsSx}>
          <Grid container spacing="30px">
            <Grid size={{ xs: 12, sm: 6 }}>
              <ViewField label="Execution Mode" value={executionMode} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <ViewField label="Scoring Target" value={scoringTarget} />
            </Grid>
          </Grid>
        </Box>
      </Box>

      <Box sx={sectionSx}>
        <FormSectionDivider headline="Test Run Metrics" />
        <Box sx={fieldsSx}>
          <ViewField
            label="Metric Source"
            value={
              metricsSource ? getMetricsSourceLabel(metricsSource) : undefined
            }
          />
          {execMetrics.length > 0 && (
            <Box>
              <Typography
                sx={{
                  fontSize: 14,
                  lineHeight: '22px',
                  color: theme => theme.palette.greyscale.subtitle,
                  px: '14px',
                  mb: '6px',
                }}
              >
                Metrics
              </Typography>
              <Box
                sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, px: '14px' }}
              >
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
        </Box>
      </Box>

      <Box sx={sectionSx}>
        <FormSectionDivider headline="Model Settings" />
        <Box sx={fieldsSx}>
          <ViewField label="Evaluation Model" value={evaluationModel} />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Switch checked={preflightEnabled} disabled size="small" />
            <Typography
              sx={{
                fontSize: 16,
                lineHeight: '24px',
                color: theme => theme.palette.greyscale.title,
              }}
            >
              Run Preflight Checks
            </Typography>
          </Box>
        </Box>
      </Box>
    </Paper>
  );
}
