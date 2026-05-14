'use client';

import * as React from 'react';
import {
  Box,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import {
  ParameterField,
  ParameterValue,
} from '@/utils/api-client/interfaces/parameters';

interface TypedValueEditorProps {
  field: ParameterField;
  value: ParameterValue | null;
  onChange: (value: ParameterValue | null) => void;
}

/**
 * Type-aware editor for one parameter slot.
 *
 * Mirrors the editor used in `ProjectParameters` for default values
 * but with required-field semantics, so the surface stays the same
 * across "edit the schema" and "fill in an experiment".
 */
export default function TypedValueEditor({
  field,
  value,
  onChange,
}: TypedValueEditorProps) {
  const label = `${field.name}${field.required ? ' *' : ''}`;
  const helper = field.description ?? undefined;

  switch (field.type) {
    case 'text': {
      const current =
        value && value.type === 'text' ? value.value : '';
      return (
        <Box>
          <TextField
            label={label}
            value={current}
            onChange={e => onChange({ type: 'text', value: e.target.value })}
            size="small"
            fullWidth
            multiline
            minRows={3}
            helperText={helper}
          />
        </Box>
      );
    }
    case 'string': {
      const current =
        value && value.type === 'string' ? value.value : '';
      return (
        <TextField
          label={label}
          value={current}
          onChange={e => onChange({ type: 'string', value: e.target.value })}
          size="small"
          fullWidth
          helperText={helper}
        />
      );
    }
    case 'integer': {
      const current =
        value && value.type === 'integer' ? value.value : '';
      return (
        <TextField
          label={label}
          type="number"
          value={current}
          onChange={e => {
            const v = e.target.value;
            onChange(
              v === '' ? null : { type: 'integer', value: parseInt(v, 10) }
            );
          }}
          size="small"
          inputProps={{ step: 1 }}
          helperText={helper}
        />
      );
    }
    case 'number': {
      const current =
        value && value.type === 'number' ? value.value : '';
      return (
        <TextField
          label={label}
          type="number"
          value={current}
          onChange={e => {
            const v = e.target.value;
            onChange(
              v === '' ? null : { type: 'number', value: parseFloat(v) }
            );
          }}
          size="small"
          inputProps={{ step: 'any' }}
          helperText={helper}
        />
      );
    }
    case 'boolean': {
      const current =
        value && value.type === 'boolean' ? value.value : false;
      return (
        <Stack>
          <FormControlLabel
            control={
              <Checkbox
                checked={current}
                onChange={e =>
                  onChange({ type: 'boolean', value: e.target.checked })
                }
              />
            }
            label={label}
          />
          {helper && (
            <Typography variant="caption" color="text.secondary">
              {helper}
            </Typography>
          )}
        </Stack>
      );
    }
    case 'enum': {
      const options = field.options ?? [];
      const current =
        value && value.type === 'enum' && options.includes(value.value)
          ? value.value
          : '';
      return (
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>{label}</InputLabel>
          <Select
            label={label}
            value={current}
            onChange={e => {
              const v = e.target.value as string;
              onChange(v ? { type: 'enum', value: v } : null);
            }}
          >
            <MenuItem value="">
              <em>(none)</em>
            </MenuItem>
            {options.map(opt => (
              <MenuItem key={opt} value={opt}>
                {opt}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      );
    }
    case 'model_ref': {
      const current =
        value && value.type === 'model_ref' ? String(value.value) : '';
      return (
        <TextField
          label={label}
          value={current}
          onChange={e => {
            const v = e.target.value.trim();
            onChange(v ? { type: 'model_ref', value: v } : null);
          }}
          size="small"
          fullWidth
          helperText={helper ?? 'UUID of a Model row'}
        />
      );
    }
    case 'secret_ref': {
      const current =
        value && value.type === 'secret_ref' ? String(value.value) : '';
      return (
        <TextField
          label={label}
          value={current}
          onChange={e => {
            const v = e.target.value.trim();
            onChange(v ? { type: 'secret_ref', value: v } : null);
          }}
          size="small"
          fullWidth
          helperText={helper ?? 'UUID of a secret record'}
        />
      );
    }
  }
}

/**
 * Render a single :class:`ParameterValue` as a short, masked-aware
 * string for read-only previews. ``secret_ref`` values are masked
 * so the preview never leaks credentials by sight.
 */
export function renderValuePreview(
  value: ParameterValue | null | undefined
): string {
  if (!value) return '—';
  switch (value.type) {
    case 'secret_ref':
      return `secret_ref: <hidden> (id ${String(value.value).slice(0, 8)}…)`;
    case 'model_ref':
      return `model_ref: ${String(value.value).slice(0, 8)}…`;
    case 'boolean':
      return value.value ? 'true' : 'false';
    case 'text':
    case 'string':
    case 'enum':
      return value.value;
    case 'integer':
    case 'number':
      return String(value.value);
  }
}
