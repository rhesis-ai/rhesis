'use client';

import React from 'react';
import {
  Autocomplete,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import { RUN_TARGET, type RunTarget } from './run-drawer-types';
import { plural } from './run-drawer-format';

/** Run one picked test set, or every test set carrying a tag. */
export function RunTargetToggle({
  value,
  onChange,
}: {
  value: RunTarget;
  onChange: (value: RunTarget) => void;
}) {
  return (
    <ToggleButtonGroup
      exclusive
      fullWidth
      value={value}
      onChange={(_, next: RunTarget | null) => next && onChange(next)}
      aria-label="What to run"
    >
      <ToggleButton value={RUN_TARGET.SET}>One test set</ToggleButton>
      <ToggleButton value={RUN_TARGET.TAG}>Sets with a tag</ToggleButton>
    </ToggleButtonGroup>
  );
}

/** Names up to three sets, then how many more. */
const describeSets = (names: string[]) =>
  names.length <= 3
    ? names.join(', ')
    : `${names.slice(0, 3).join(', ')} and ${names.length - 3} more`;

export function TestSetTagField({
  tags,
  value,
  onChange,
  setNames,
  loading,
}: {
  /** Tag names carried by at least one test set. */
  tags: string[];
  value: string | null;
  onChange: (value: string | null) => void;
  /** The sets carrying the picked tag. */
  setNames: string[];
  loading: boolean;
}) {
  const helperText = !value
    ? 'Every test set carrying the tag runs, each as its own test run.'
    : loading
      ? 'Finding the test sets…'
      : setNames.length === 0
        ? 'No test sets carry this tag.'
        : `${plural(setNames.length, 'test set')}: ${describeSets(setNames)}`;

  return (
    <Autocomplete
      options={tags}
      value={value}
      onChange={(_, next) => onChange(next)}
      fullWidth
      renderInput={params => (
        <TextField
          {...params}
          label="Test set tag"
          required
          helperText={helperText}
        />
      )}
    />
  );
}
