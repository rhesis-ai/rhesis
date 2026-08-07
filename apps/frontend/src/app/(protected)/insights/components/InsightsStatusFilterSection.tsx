'use client';

import * as React from 'react';
import { Box, Checkbox, Link, Typography } from '@mui/material';
import { FilterSection } from '@/components/common/FilterDrawer';

const DEFAULT_VISIBLE_COUNT = 5;

const checkboxSx = {
  p: '9px',
  mr: 0,
  '& .MuiSvgIcon-root': {
    fontSize: 20,
  },
} as const;

export interface InsightsStatusOption {
  id: string;
  name: string;
}

interface InsightsStatusFilterSectionProps {
  options: InsightsStatusOption[];
  checkedIds: string[];
  onCheckedIdsChange: (ids: string[]) => void;
}

function StatusCheckboxRow({
  option,
  checked,
  onToggle,
}: {
  option: InsightsStatusOption;
  checked: boolean;
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
        onChange={onToggle}
        sx={checkboxSx}
        inputProps={{ 'aria-label': option.name }}
      />
      <Typography
        sx={{
          fontSize: 14,
          lineHeight: '22px',
          color: theme => theme.palette.greyscale.title,
          wordBreak: 'break-word',
        }}
      >
        {option.name}
      </Typography>
    </Box>
  );
}

export default function InsightsStatusFilterSection({
  options,
  checkedIds,
  onCheckedIdsChange,
}: InsightsStatusFilterSectionProps) {
  const [showAll, setShowAll] = React.useState(false);

  if (options.length === 0) {
    return null;
  }

  const visibleOptions =
    showAll || options.length <= DEFAULT_VISIBLE_COUNT
      ? options
      : options.slice(0, DEFAULT_VISIBLE_COUNT);

  const toggleStatus = (id: string) => {
    onCheckedIdsChange(
      checkedIds.includes(id)
        ? checkedIds.filter(value => value !== id)
        : [...checkedIds, id]
    );
  };

  return (
    <FilterSection title="Status">
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <Typography
            sx={{
              fontSize: 14,
              lineHeight: '22px',
              color: theme => theme.palette.greyscale.body,
            }}
          >
            Status
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: 'column' }}>
            {visibleOptions.map(option => (
              <StatusCheckboxRow
                key={option.id}
                option={option}
                checked={checkedIds.includes(option.id)}
                onToggle={() => toggleStatus(option.id)}
              />
            ))}
          </Box>
        </Box>

        {!showAll && options.length > DEFAULT_VISIBLE_COUNT ? (
          <Link
            component="button"
            type="button"
            underline="always"
            onClick={() => setShowAll(true)}
            sx={{
              alignSelf: 'flex-start',
              fontSize: 14,
              lineHeight: '22px',
              color: theme => theme.palette.greyscale.body,
              cursor: 'pointer',
              textUnderlineOffset: '2px',
            }}
          >
            Show all
          </Link>
        ) : null}
      </Box>
    </FilterSection>
  );
}
