'use client';

import React from 'react';
import {
  Autocomplete,
  Box,
  Chip,
  FormControl,
  FormHelperText,
  TextField,
} from '@mui/material';
import type { UUID } from 'crypto';
import { drawerDisabledFieldSx } from '@/components/common/drawerFormFieldSx';
import type { TestSet } from '@/utils/api-client/interfaces/test-set';

export interface EndpointOption {
  id: UUID;
  name: string;
  environment?: 'development' | 'staging' | 'production' | 'local';
  project_id?: string;
  organization_id?: string;
  connection_type?: string;
}

/** A value the current mode doesn't let you change, shown as a disabled field. */
export function FixedField({ label, value }: { label: string; value: string }) {
  return (
    <TextField
      label={label}
      value={value}
      disabled
      fullWidth
      InputLabelProps={{ shrink: true }}
      sx={drawerDisabledFieldSx}
    />
  );
}

const ENVIRONMENT_COLOR = {
  production: 'error',
  staging: 'warning',
  development: 'success',
  local: 'success',
} as const;

export function EndpointField({
  endpoints,
  value,
  onChange,
  loading,
}: {
  endpoints: EndpointOption[];
  value: UUID | null;
  onChange: (id: UUID | null) => void;
  loading: boolean;
}) {
  return (
    <FormControl fullWidth>
      <Autocomplete
        options={endpoints}
        value={endpoints.find(e => e.id === value) || null}
        onChange={(_, v) => onChange(v?.id ?? null)}
        getOptionLabel={opt => opt.name}
        renderInput={params => (
          <TextField
            {...params}
            label="Endpoint"
            required
            placeholder="Select endpoint"
          />
        )}
        renderOption={(props, option) => {
          const { key: _key, ...otherProps } = props;
          return (
            <Box
              key={option.id}
              {...otherProps}
              component="li"
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span>{option.name}</span>
              {option.environment && (
                <Chip
                  label={option.environment}
                  size="small"
                  color={ENVIRONMENT_COLOR[option.environment]}
                  sx={{ ml: 1 }}
                />
              )}
            </Box>
          );
        }}
        isOptionEqualToValue={(a, b) => a.id === b.id}
      />
      {endpoints.length === 0 && !loading && (
        <FormHelperText>No endpoints available for this project</FormHelperText>
      )}
    </FormControl>
  );
}

const testSetLabel = (testSet: TestSet) => testSet.name || 'Unnamed Test Set';

export function TestSetField({
  testSets,
  value,
  onChange,
}: {
  testSets: TestSet[];
  value: TestSet | null;
  onChange: (testSet: TestSet | null) => void;
}) {
  return (
    <Autocomplete
      options={testSets}
      value={value}
      onChange={(_, v) => onChange(v)}
      getOptionLabel={testSetLabel}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      renderOption={(props, option) => {
        const { key: _key, ...otherProps } = props;
        return (
          <Box component="li" key={option.id} {...otherProps}>
            {testSetLabel(option)}
          </Box>
        );
      }}
      fullWidth
      renderInput={params => (
        <TextField {...params} label="Test Set" required />
      )}
    />
  );
}
