import { FormControlLabel, Switch, Typography } from '@mui/material';

interface SelectionModeToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** e.g. "Select tests", "Select endpoints". */
  label: string;
}

/**
 * The "Select X" switch that reveals a grid's checkbox column, extracted
 * from TestsGrid so every grid's toolbar renders the identical control
 * instead of a copy of the same Switch + FormControlLabel block.
 */
export default function SelectionModeToggle({
  checked,
  onChange,
  label,
}: SelectionModeToggleProps) {
  return (
    <FormControlLabel
      control={
        <Switch
          checked={checked}
          onChange={event => onChange(event.target.checked)}
          size="small"
          color="primary"
        />
      }
      label={
        <Typography variant="button" color="primary">
          {label}
        </Typography>
      }
      sx={{ m: 0, whiteSpace: 'nowrap' }}
    />
  );
}
