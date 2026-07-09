'use client';

import * as React from 'react';
import { Box, Checkbox, Link, Typography } from '@mui/material';
import { FilterSection } from '@/components/common/FilterDrawer';
import { InsightsBehaviorOption } from '../utils/insights-filter-utils';

const DEFAULT_VISIBLE_COUNT = 5;

const checkboxSx = {
  p: '9px',
  mr: 0,
  '& .MuiSvgIcon-root': {
    fontSize: 20,
  },
} as const;

interface InsightsBehaviorFilterSectionProps {
  options: InsightsBehaviorOption[];
  checkedIds: string[];
  onCheckedIdsChange: (ids: string[]) => void;
}

function BehaviorCheckboxRow({
  option,
  checked,
  onToggle,
}: {
  option: InsightsBehaviorOption;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        minHeight: 38,
        width: '100%',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          minWidth: 0,
          flex: 1,
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
      <Typography
        sx={{
          fontSize: 14,
          lineHeight: '22px',
          color: theme => theme.palette.greyscale.subtitle,
          flexShrink: 0,
          pl: 2,
          textAlign: 'right',
          minWidth: 24,
        }}
      >
        {option.count}
      </Typography>
    </Box>
  );
}

export default function InsightsBehaviorFilterSection({
  options,
  checkedIds,
  onCheckedIdsChange,
}: InsightsBehaviorFilterSectionProps) {
  const [showAll, setShowAll] = React.useState(false);

  if (options.length === 0) {
    return null;
  }

  const visibleOptions =
    showAll || options.length <= DEFAULT_VISIBLE_COUNT
      ? options
      : options.slice(0, DEFAULT_VISIBLE_COUNT);

  const toggleBehavior = (id: string) => {
    onCheckedIdsChange(
      checkedIds.includes(id)
        ? checkedIds.filter(value => value !== id)
        : [...checkedIds, id]
    );
  };

  return (
    <FilterSection title="Behaviors">
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <Typography
            sx={{
              fontSize: 14,
              lineHeight: '22px',
              color: theme => theme.palette.greyscale.body,
            }}
          >
            Behavior
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: 'column' }}>
            {visibleOptions.map(option => (
              <BehaviorCheckboxRow
                key={option.id}
                option={option}
                checked={checkedIds.includes(option.id)}
                onToggle={() => toggleBehavior(option.id)}
              />
            ))}
          </Box>

          <Typography
            sx={{
              fontSize: 12,
              lineHeight: '18px',
              color: 'text.secondary',
              pt: '3px',
            }}
          >
            Uncheck behaviors to hide them from the pass rate view.
          </Typography>
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
