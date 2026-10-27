'use client';

import React, { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  FormControl,
  IconButton,
  InputLabel,
  Link as MuiLink,
  MenuItem,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import {
  Add as AddIcon,
  AutoGraph as AutoGraphIcon,
  Bolt as BoltIcon,
  Close as CloseIcon,
  Edit as EditIcon,
  Psychology as PsychologyIcon,
  Replay as ReplayIcon,
  Tune as TuneIcon,
} from '@mui/icons-material';
import Link from 'next/link';
import type { UUID } from 'crypto';
import {
  drawerOutlineButtonSx,
  drawerOutlinedFieldSx,
} from '@/components/common/drawerFormFieldSx';
import SelectMetricsDialog from '@/components/common/SelectMetricsDialog';
import type { LastTestRunSummary } from '@/utils/api-client/interfaces/test-set';
import { formatDate } from '@/utils/date';
import { BORDER_RADIUS } from '@/styles/theme';
import {
  METRIC_MODE,
  SCORING_TARGET,
  type MetricMode,
  type ScoringTarget,
  type SelectedMetric,
} from './run-drawer-types';

/** A select option with an icon, a label and a one-line explanation. */
function OptionRow({
  icon,
  label,
  caption,
}: {
  icon: React.ReactNode;
  label: string;
  caption: string;
}) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {icon}
      <Box>
        <Typography variant="body1">{label}</Typography>
        <Typography variant="caption" color="text.secondary">
          {caption}
        </Typography>
      </Box>
    </Box>
  );
}

interface MetricsFieldProps {
  metricMode: MetricMode;
  onMetricModeChange: (mode: MetricMode) => void;
  testSetMetricCount: number;
  selectedMetrics: SelectedMetric[];
  onAddMetric: (metric: {
    id: UUID;
    name: string;
  }) => void;
  onRemoveMetric: (id: UUID) => void;
  testType?: string;
}

export function MetricsField({
  metricMode,
  onMetricModeChange,
  testSetMetricCount,
  selectedMetrics,
  onAddMetric,
  onRemoveMetric,
  testType,
}: MetricsFieldProps) {
  const labelId = React.useId();
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <>
      <FormControl fullWidth sx={drawerOutlinedFieldSx}>
        <InputLabel id={labelId} shrink>
          Metrics Source
        </InputLabel>
        <Select
          labelId={labelId}
          value={metricMode}
          onChange={e => onMetricModeChange(e.target.value as MetricMode)}
          label="Metrics Source"
          notched
        >
          {testSetMetricCount > 0 && (
            <MenuItem value={METRIC_MODE.TEST_SET}>
              <OptionRow
                icon={<TuneIcon fontSize="small" />}
                label="Test Set Metrics"
                caption={`Use ${testSetMetricCount} metric${testSetMetricCount !== 1 ? 's' : ''} configured on this test set`}
              />
            </MenuItem>
          )}
          <MenuItem value={METRIC_MODE.REQUIREMENT}>
            <OptionRow
              icon={<PsychologyIcon fontSize="small" />}
              label="Requirement Metrics"
              caption="Use default metrics defined on each test's requirement"
            />
          </MenuItem>
          <MenuItem value={METRIC_MODE.CUSTOM}>
            <OptionRow
              icon={<EditIcon fontSize="small" />}
              label="Custom Metrics"
              caption="Define specific metrics for this execution only"
            />
          </MenuItem>
        </Select>
      </FormControl>

      {metricMode === METRIC_MODE.CUSTOM && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Alert severity="info">
            These metrics will only be used for this specific execution and will
            not be saved to the test set.
          </Alert>

          {selectedMetrics.length > 0 && (
            <Stack spacing={1}>
              {selectedMetrics.map(metric => (
                <Box
                  key={metric.id}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    p: 1,
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: BORDER_RADIUS.sm,
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <AutoGraphIcon fontSize="small" color="primary" />
                    <Typography variant="body2">{metric.name}</Typography>
                  </Box>
                  <IconButton
                    aria-label={`Remove ${metric.name}`}
                    size="small"
                    onClick={() => onRemoveMetric(metric.id)}
                  >
                    <CloseIcon fontSize="small" />
                  </IconButton>
                </Box>
              ))}
            </Stack>
          )}

          <Button
            variant="outlined"
            fullWidth
            startIcon={<AddIcon />}
            onClick={() => setDialogOpen(true)}
            sx={drawerOutlineButtonSx}
          >
            Add metric
          </Button>

          <SelectMetricsDialog
            open={dialogOpen}
            onClose={() => setDialogOpen(false)}
            onSelect={onAddMetric}
            excludeMetricIds={selectedMetrics.map(m => m.id)}
            title="Add Metric to Execution"
            subtitle="Select a metric to use for this test run"
            testType={testType}
            variant="drawer"
          />
        </Box>
      )}
    </>
  );
}

interface ScoringTargetFieldProps {
  value: ScoringTarget;
  onChange: (value: ScoringTarget) => void;
  /** What "Reuse Outputs" would re-score, or why it can't. */
  reuseCaption: string;
  reuseDisabled: boolean;
  /** The run whose outputs are reused, linked from the note under the field. */
  reusedRun?: LastTestRunSummary | null;
  /** Re-run mode: the outputs come from the run being re-run. */
  reusingThisRun?: boolean;
}

export function ScoringTargetField({
  value,
  onChange,
  reuseCaption,
  reuseDisabled,
  reusedRun,
  reusingThisRun = false,
}: ScoringTargetFieldProps) {
  const labelId = React.useId();
  return (
    <>
      <FormControl fullWidth sx={drawerOutlinedFieldSx}>
        <InputLabel id={labelId} shrink>
          Scoring Target
        </InputLabel>
        <Select
          labelId={labelId}
          value={value}
          onChange={e => onChange(e.target.value as ScoringTarget)}
          label="Scoring Target"
          notched
        >
          <MenuItem value={SCORING_TARGET.FRESH}>
            <OptionRow
              icon={<BoltIcon fontSize="small" />}
              label="Fresh Outputs"
              caption="Call the endpoint and score the new responses"
            />
          </MenuItem>
          <MenuItem value={SCORING_TARGET.REUSE} disabled={reuseDisabled}>
            <OptionRow
              icon={<ReplayIcon fontSize="small" />}
              label="Reuse Outputs"
              caption={reuseCaption}
            />
          </MenuItem>
        </Select>
      </FormControl>

      {value === SCORING_TARGET.REUSE && reusedRun && (
        <Alert severity="info">
          Outputs from{' '}
          <MuiLink
            component={Link}
            href={`/test-runs/${reusedRun.nano_id || reusedRun.id}`}
            target="_blank"
            fontWeight="fontWeightBold"
          >
            {reusedRun.name ||
              `Test run from ${
                reusedRun.created_at
                  ? formatDate(reusedRun.created_at)
                  : 'unknown date'
              }`}
          </MuiLink>{' '}
          ({reusedRun.pass_rate}% pass rate, {reusedRun.test_count} tests) will
          be reused. Only metrics will be re-evaluated.
        </Alert>
      )}

      {value === SCORING_TARGET.REUSE && reusingThisRun && (
        <Alert severity="info">
          Outputs from this test run will be reused. Only metrics will be
          re-evaluated.
        </Alert>
      )}
    </>
  );
}
