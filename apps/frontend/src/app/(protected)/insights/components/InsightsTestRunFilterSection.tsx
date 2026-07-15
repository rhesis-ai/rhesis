'use client';

import * as React from 'react';
import {
  Box,
  Checkbox,
  CircularProgress,
  Link,
  Typography,
} from '@mui/material';
import { FilterSection } from '@/components/common/FilterDrawer';
import { InsightsTestRunOption } from '../utils/insights-filter-utils';

const DEFAULT_VISIBLE_COUNT = 5;

const checkboxSx = {
  p: '9px',
  mr: 0,
  '& .MuiSvgIcon-root': {
    fontSize: 20,
  },
} as const;

interface InsightsTestRunFilterSectionProps {
  options: InsightsTestRunOption[];
  checkedIds: string[];
  onCheckedIdsChange: (ids: string[]) => void;
  loading?: boolean;
  disabled?: boolean;
  /** When true, render only the list (parent supplies section chrome). */
  embedded?: boolean;
}

function TestRunCheckboxRow({
  option,
  checked,
  disabled,
  onToggle,
}: {
  option: InsightsTestRunOption;
  checked: boolean;
  disabled?: boolean;
  onToggle: () => void;
}) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        minHeight: 38,
        width: '100%',
      }}
    >
      <Checkbox
        checked={checked}
        disabled={disabled}
        onChange={onToggle}
        sx={checkboxSx}
        inputProps={{ 'aria-label': option.label }}
      />
      <Typography
        sx={{
          fontSize: 14,
          lineHeight: '22px',
          color: theme => theme.palette.greyscale.title,
          wordBreak: 'break-word',
        }}
      >
        {option.label}
      </Typography>
    </Box>
  );
}

export default function InsightsTestRunFilterSection({
  options,
  checkedIds,
  onCheckedIdsChange,
  loading = false,
  disabled = false,
  embedded = false,
}: InsightsTestRunFilterSectionProps) {
  const [showAll, setShowAll] = React.useState(false);

  const visibleOptions =
    showAll || options.length <= DEFAULT_VISIBLE_COUNT
      ? options
      : options.slice(0, DEFAULT_VISIBLE_COUNT);

  const toggleTestRun = (id: string) => {
    if (disabled) return;
    onCheckedIdsChange(
      checkedIds.includes(id)
        ? checkedIds.filter(value => value !== id)
        : [...checkedIds, id]
    );
  };

  const content = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {!embedded ? (
          <Typography
            sx={{
              fontSize: 14,
              lineHeight: '22px',
              color: theme => theme.palette.greyscale.body,
            }}
          >
            Test run
          </Typography>
        ) : null}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
            <CircularProgress size={24} />
          </Box>
        ) : options.length === 0 ? (
          <Typography
            sx={{
              fontSize: 14,
              lineHeight: '22px',
              color: 'text.secondary',
            }}
          >
            {disabled
              ? 'Select an endpoint to view test runs.'
              : 'No test runs found for this endpoint.'}
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column' }}>
            {visibleOptions.map(option => (
              <TestRunCheckboxRow
                key={option.id}
                option={option}
                checked={checkedIds.includes(option.id)}
                disabled={disabled}
                onToggle={() => toggleTestRun(option.id)}
              />
            ))}
          </Box>
        )}

        <Typography
          sx={{
            fontSize: 12,
            lineHeight: '18px',
            color: 'text.secondary',
            pt: '3px',
          }}
        >
          All runs are included by default. Uncheck runs to narrow the view.
        </Typography>
      </Box>

      {!loading && !showAll && options.length > DEFAULT_VISIBLE_COUNT ? (
        <Link
          component="button"
          type="button"
          underline="always"
          disabled={disabled}
          onClick={() => {
            if (!disabled) setShowAll(true);
          }}
          sx={{
            alignSelf: 'flex-start',
            fontSize: 14,
            lineHeight: '22px',
            color: theme => theme.palette.greyscale.body,
            cursor: disabled ? 'default' : 'pointer',
            textUnderlineOffset: '2px',
            opacity: disabled ? 0.5 : 1,
            pointerEvents: disabled ? 'none' : 'auto',
          }}
        >
          Show all
        </Link>
      ) : null}
    </Box>
  );

  if (embedded) {
    return content;
  }

  return <FilterSection title="Test runs">{content}</FilterSection>;
}
