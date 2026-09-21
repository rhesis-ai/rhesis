'use client';

import React from 'react';
import {
  FormControl,
  IconButton,
  InputLabel,
  Link,
  MenuItem,
  Select,
  Stack,
  TextField,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import type { ToolProvider } from '@/utils/api-client/interfaces/tool-provider';
import { OPTION_FIELDS, adapterKey } from './adapters';
import { MASKED, isMasked, visibleFields, type FieldValues } from './values';

/** A choice offered by the provider itself, e.g. a Jira project. */
export interface FieldOption {
  key: string;
  name: string;
}

interface ProviderFieldsProps {
  manifest: ToolProvider;
  values: FieldValues;
  onChange: (key: string, value: string) => void;
  /** Options for select-backed fields, keyed by field key. */
  options?: Record<string, FieldOption[]>;
  disabled?: boolean;
}

/**
 * Renders a provider's fields from its manifest.
 *
 * Replaces the per-provider blocks that used to make up most of the connection
 * drawer. Nothing here knows a provider's name: what to show, whether to mask
 * it and whether it is required all come from the manifest, and the handful of
 * inputs that are not plain text boxes are declared in `adapters.ts`.
 */
export function ProviderFields({
  manifest,
  values,
  onChange,
  options = {},
  disabled = false,
}: ProviderFieldsProps) {
  const [revealed, setRevealed] = React.useState<Record<string, boolean>>({});

  return (
    <Stack spacing={3}>
      {visibleFields(manifest).map(field => {
        const value = values[field.key] ?? '';
        const isOption = OPTION_FIELDS.has(adapterKey(manifest.key, field.key));
        const fieldOptions = options[field.key] ?? [];

        if (isOption && fieldOptions.length > 0) {
          return (
            <FormControl fullWidth key={field.key} disabled={disabled}>
              <InputLabel id={`field-${field.key}`}>{field.label}</InputLabel>
              <Select
                labelId={`field-${field.key}`}
                label={field.label}
                value={fieldOptions.some(o => o.key === value) ? value : ''}
                onChange={e => onChange(field.key, e.target.value)}
              >
                {fieldOptions.map(option => (
                  <MenuItem key={option.key} value={option.key}>
                    {option.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          );
        }

        const showReveal = field.secret && !isMasked(value);
        return (
          <TextField
            key={field.key}
            label={field.label}
            fullWidth
            required={field.required}
            disabled={disabled}
            value={value}
            placeholder={field.placeholder || undefined}
            type={field.secret && !revealed[field.key] ? 'password' : 'text'}
            // A masked value stands for a stored credential the form cannot
            // read. Clear it on focus so typing replaces it rather than
            // appending to a row of asterisks.
            onFocus={() => {
              if (isMasked(value)) onChange(field.key, '');
            }}
            onChange={e => onChange(field.key, e.target.value)}
            helperText={helperFor(field.help_text, field.help_url)}
            slotProps={{
              input: showReveal
                ? {
                    endAdornment: (
                      <IconButton
                        aria-label={`Show ${field.label}`}
                        onClick={() =>
                          setRevealed(prev => ({
                            ...prev,
                            [field.key]: !prev[field.key],
                          }))
                        }
                        edge="end"
                      >
                        {revealed[field.key] ? (
                          <VisibilityOffIcon />
                        ) : (
                          <VisibilityIcon />
                        )}
                      </IconButton>
                    ),
                  }
                : undefined,
            }}
          />
        );
      })}
    </Stack>
  );
}

function helperFor(
  helpText: string,
  helpUrl: string
): React.ReactNode | undefined {
  if (!helpText && !helpUrl) return undefined;
  if (!helpUrl) return helpText;
  return (
    <>
      {helpText ? `${helpText} ` : null}
      <Link href={helpUrl} target="_blank" rel="noopener noreferrer">
        How to get this
      </Link>
    </>
  );
}

export { MASKED };
