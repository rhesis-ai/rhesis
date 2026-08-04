'use client';

import * as React from 'react';
import { FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterDrawerSelectSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import { getUsagePeriodOptions } from '@/utils/usagePeriods';

// MUI's Select needs a defined `value` for every option -- `null` (our
// "current period" sentinel) can't be one, so it's swapped for this string
// at the component boundary and back on change.
const CURRENT_PERIOD_OPTION_VALUE = '__current__';

interface UsageOverviewFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  periodStart: string | null;
  onApply: (periodStart: string | null) => void;
}

export default function UsageOverviewFilterDrawer({
  open,
  onClose,
  periodStart,
  onApply,
}: UsageOverviewFilterDrawerProps) {
  const options = React.useMemo(() => getUsagePeriodOptions(), []);
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft<
    string | null
  >(open, periodStart, null, onApply, onClose);

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Billing Period">
        <FormControl fullWidth size="small">
          <InputLabel id="usage-overview-period-label">Period</InputLabel>
          <Select
            labelId="usage-overview-period-label"
            value={draft ?? CURRENT_PERIOD_OPTION_VALUE}
            label="Period"
            onChange={e =>
              setDraft(
                e.target.value === CURRENT_PERIOD_OPTION_VALUE
                  ? null
                  : e.target.value
              )
            }
            sx={filterDrawerSelectSx}
          >
            {options.map(option => (
              <MenuItem
                key={option.value ?? CURRENT_PERIOD_OPTION_VALUE}
                value={option.value ?? CURRENT_PERIOD_OPTION_VALUE}
              >
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </FilterSection>
    </FilterDrawerShell>
  );
}
