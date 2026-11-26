'use client';

import React from 'react';
import {
  Box,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  Typography,
} from '@mui/material';
import {
  ArrowForward as ArrowForwardIcon,
  CallSplit as CallSplitIcon,
} from '@mui/icons-material';
import { drawerOutlinedFieldSx } from '@/components/common/drawerFormFieldSx';
import { EXECUTION_MODE } from './run-drawer-types';

const EXECUTION_MODE_OPTIONS = [
  {
    value: EXECUTION_MODE.PARALLEL,
    icon: <CallSplitIcon fontSize="small" />,
    caption: 'Tests run simultaneously for faster execution (default)',
  },
  {
    value: EXECUTION_MODE.SEQUENTIAL,
    icon: <ArrowForwardIcon fontSize="small" />,
    caption: 'Tests run one after another, better for rate-limited endpoints',
  },
];

export function ExecutionModeField({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const labelId = React.useId();
  return (
    <FormControl fullWidth sx={drawerOutlinedFieldSx}>
      <InputLabel id={labelId} shrink>
        Execution Mode
      </InputLabel>
      <Select
        labelId={labelId}
        value={value}
        onChange={e => onChange(e.target.value)}
        label="Execution Mode"
        notched
      >
        {EXECUTION_MODE_OPTIONS.map(option => (
          <MenuItem key={option.value} value={option.value}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {option.icon}
              <Box>
                <Typography variant="body1">{option.value}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {option.caption}
                </Typography>
              </Box>
            </Box>
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}

export function PreflightField({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <FormControlLabel
      sx={{ mx: 0, justifyContent: 'space-between', gap: 2 }}
      labelPlacement="start"
      control={
        <Switch checked={checked} onChange={e => onChange(e.target.checked)} />
      }
      label={
        <Box>
          <Typography variant="body1">Run Preflight Checks</Typography>
          <Typography variant="caption" color="text.secondary">
            {checked
              ? 'Validate endpoint and model configuration before executing'
              : 'Skip validation and start the run immediately'}
          </Typography>
        </Box>
      }
    />
  );
}
