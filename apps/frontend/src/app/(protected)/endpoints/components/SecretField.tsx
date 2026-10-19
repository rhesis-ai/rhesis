'use client';

import React, { useState } from 'react';
import { IconButton, InputAdornment, TextField } from '@mui/material';
import {
  DeleteIcon,
  LockIcon,
  RefreshIcon,
  VisibilityIcon,
  VisibilityOffIcon,
} from '@/components/icons';

const STORED_MASK = '••••••••••••••••••••••••';

export interface SecretFieldProps {
  label: string;
  // used in button labels, e.g. "token" -> "remove token"
  noun: string;
  // '' means "keep the stored value"
  value: string;
  onChange: (value: string) => void;
  hasStored?: boolean;
  required?: boolean;
  placeholder?: string;
  helperText?: React.ReactNode;
  // Clearing is offered only when both are given.
  cleared?: boolean;
  onToggleCleared?: () => void;
}

/** A write-only secret: masked when one is stored, never shown back. */
export default function SecretField({
  label,
  noun,
  value,
  onChange,
  hasStored = false,
  required = false,
  placeholder,
  helperText,
  cleared = false,
  onToggleCleared,
}: SecretFieldProps) {
  const [visible, setVisible] = useState(false);
  const [focused, setFocused] = useState(false);

  const shown = cleared
    ? ''
    : focused || value !== ''
      ? value
      : hasStored
        ? STORED_MASK
        : '';

  return (
    <TextField
      fullWidth
      label={label}
      required={required && !hasStored}
      type={visible ? 'text' : 'password'}
      value={shown}
      onChange={e => onChange(e.target.value)}
      onFocus={() => setFocused(true)}
      onBlur={() => {
        if (value === '') setFocused(false);
      }}
      placeholder={
        cleared
          ? `The saved ${noun} will be removed on save`
          : hasStored
            ? `Enter a new ${noun} or leave empty to keep the existing one`
            : placeholder
      }
      error={cleared}
      helperText={
        cleared
          ? `The saved ${noun} will be removed when you save. Type a new one or restore to keep it.`
          : hasStored
            ? `Leave empty to keep the existing ${noun}, or enter a new one to replace it.`
            : helperText
      }
      InputProps={{
        startAdornment: (
          <InputAdornment position="start">
            <LockIcon color="action" />
          </InputAdornment>
        ),
        endAdornment: (
          <InputAdornment position="end">
            {hasStored && value === '' && onToggleCleared && (
              <IconButton
                aria-label={cleared ? `restore ${noun}` : `remove ${noun}`}
                title={cleared ? `Restore ${noun}` : `Remove ${noun}`}
                onClick={onToggleCleared}
                edge="end"
              >
                {cleared ? <RefreshIcon /> : <DeleteIcon />}
              </IconButton>
            )}
            <IconButton
              aria-label={`toggle ${noun} visibility`}
              onClick={() => setVisible(v => !v)}
              edge="end"
            >
              {visible ? <VisibilityOffIcon /> : <VisibilityIcon />}
            </IconButton>
          </InputAdornment>
        ),
      }}
    />
  );
}

export { STORED_MASK };
