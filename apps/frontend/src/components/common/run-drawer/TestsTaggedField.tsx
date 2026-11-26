'use client';

import React from 'react';
import { Autocomplete, Box, Chip, TextField, Typography } from '@mui/material';
import type { TestSetTestTag } from '@/utils/api-client/interfaces/test-set';
import { plural } from './run-drawer-format';

/** Run only the tests carrying any of the chosen tags. Empty runs every test. */
export default function TestsTaggedField({
  tags,
  value,
  onChange,
}: {
  /** The tags on the chosen sets' tests, with how many tests carry each. */
  tags: TestSetTestTag[];
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const countOf = new Map(tags.map(tag => [tag.name, tag.test_count]));
  // A re-run or schedule can name a tag no test carries any more; keep it visible.
  const options = [
    ...tags.map(tag => tag.name),
    ...value.filter(name => !countOf.has(name)),
  ];

  return (
    <Autocomplete
      multiple
      options={options}
      value={value}
      onChange={(_, next) => onChange(next)}
      renderOption={(props, option) => {
        const { key: _key, ...otherProps } = props;
        return (
          <Box
            component="li"
            key={option}
            {...otherProps}
            sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}
          >
            <span>{option}</span>
            <Typography variant="body2" color="text.secondary">
              {plural(countOf.get(option) ?? 0, 'test')}
            </Typography>
          </Box>
        );
      }}
      renderValue={(selected, getItemProps) =>
        selected.map((option, index) => {
          const { key, ...itemProps } = getItemProps({ index });
          return <Chip key={key} label={option} size="small" {...itemProps} />;
        })
      }
      fullWidth
      renderInput={params => (
        <TextField
          {...params}
          label="Only tests tagged"
          placeholder={value.length === 0 ? 'All tests' : undefined}
          helperText="Runs the tests carrying any of these tags. Leave empty to run every test."
          InputLabelProps={{ shrink: true }}
        />
      )}
    />
  );
}
