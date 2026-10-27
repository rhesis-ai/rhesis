'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import type { MetricTargetChoice } from '@/utils/api-client/interfaces/metric';
import { getMetricTargetIcon } from '@/utils/metric-targets';

export interface MetricTargetValue {
  on: string;
  /** Only used by per-span targets. */
  name: string;
}

interface MetricTargetPickerProps {
  choices: MetricTargetChoice[];
  value: MetricTargetValue;
  onChange: (value: MetricTargetValue) => void;
}

/** One chip per target the metric can take, plus a name field for per-span targets. */
export default function MetricTargetPicker({
  choices,
  value,
  onChange,
}: MetricTargetPickerProps) {
  const selected = choices.find(c => c.on === value.on);

  return (
    <Box>
      <Box
        sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}
        role="radiogroup"
        aria-label="Judges"
      >
        {choices.map(choice => {
          const isSelected = choice.on === value.on;
          return (
            <Tooltip key={choice.on} title={choice.description} describeChild>
              <Chip
                role="radio"
                aria-checked={isSelected}
                icon={getMetricTargetIcon(choice.on)}
                label={choice.label}
                clickable
                color={isSelected ? 'primary' : 'default'}
                variant={isSelected ? 'filled' : 'outlined'}
                onClick={() => onChange({ ...value, on: choice.on })}
              />
            </Tooltip>
          );
        })}
      </Box>
      {selected && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mt: 1 }}
          data-testid="metric-target-description"
        >
          {selected.description}
        </Typography>
      )}
      {selected?.per_span && (
        <TextField
          sx={{ mt: 2 }}
          fullWidth
          size="small"
          label="Name"
          value={value.name}
          onChange={e => onChange({ ...value, name: e.target.value })}
          helperText="Optional. Only judge spans with this tool, agent or model name."
        />
      )}
    </Box>
  );
}
