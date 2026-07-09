'use client';

import React from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  type SelectChangeEvent,
  Typography,
} from '@mui/material';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import {
  type EndpointOption,
  formatEndpointLabel,
  formatEnvironment,
  getEnvironmentColor,
} from '@/utils/endpoint-options';

export interface EndpointSelectFieldProps {
  label: string;
  placeholder: string;
  value: string | null;
  onChange: (endpointId: string | null) => void;
  options: EndpointOption[];
  /** Shown below the field when an endpoint is selected */
  helperText?: string;
  selectId?: string;
}

export default function EndpointSelectField({
  label,
  placeholder,
  value,
  onChange,
  options,
  helperText,
  selectId = 'endpoint-select',
}: EndpointSelectFieldProps) {
  const labelId = `${selectId}-label`;

  const handleChange = (event: SelectChangeEvent<string>) => {
    const next = event.target.value;
    onChange(next === '' ? null : next);
  };

  return (
    <FormControl fullWidth>
      <InputLabel id={labelId}>{label}</InputLabel>
      <Select
        labelId={labelId}
        id={selectId}
        value={value ?? ''}
        label={label}
        displayEmpty
        onChange={handleChange}
        renderValue={selected => {
          if (!selected) {
            return (
              <Typography variant="body2" color="text.secondary">
                {placeholder}
              </Typography>
            );
          }
          const option = options.find(o => o.endpointId === selected);
          return option ? formatEndpointLabel(option) : selected;
        }}
      >
        <MenuItem value="">
          <Typography variant="body2" color="text.secondary">
            {placeholder}
          </Typography>
        </MenuItem>
        {options.map(option => (
          <MenuItem key={option.endpointId} value={option.endpointId}>
            <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <Typography variant="body2" sx={{ flexGrow: 1 }}>
                {formatEndpointLabel(option)}
              </Typography>
              <Typography
                component="span"
                variant="caption"
                sx={{
                  ml: 2,
                  px: 1,
                  py: 0.25,
                  borderRadius: BORDER_RADIUS.pill,
                  bgcolor: theme => theme.palette.greyscale.surface2,
                  color: getEnvironmentColor(option.environment),
                  fontWeight: 600,
                }}
              >
                {formatEnvironment(option.environment)}
              </Typography>
            </Box>
          </MenuItem>
        ))}
      </Select>
      {value && helperText && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
          {helperText}
        </Typography>
      )}
    </FormControl>
  );
}
