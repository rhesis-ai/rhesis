'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import { FilterSection } from '@/components/common/FilterDrawer';
import type {
  ActivityPresenceFilters,
  PresenceFilterValue,
} from './presence-filter';

const PRESENCE_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'with', label: 'With' },
  { value: 'without', label: 'Without' },
] as const;

interface PresenceFilterRowProps {
  label: string;
  tabs: { value: string; label: string }[];
  activeValue: string;
  onChange: (value: PresenceFilterValue) => void;
}

function PresenceFilterRow({
  label,
  tabs,
  activeValue,
  onChange,
}: PresenceFilterRowProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 2,
      }}
    >
      <Typography
        sx={{
          fontSize: 14,
          color: theme => theme.palette.greyscale.body,
          flexShrink: 0,
        }}
      >
        {label}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
        {tabs.map(({ value, label: tabLabel }, idx, arr) => {
          const isSelected = activeValue === value;
          const isFirst = idx === 0;
          const isLast = idx === arr.length - 1;

          return (
            <Box
              key={value}
              component="button"
              type="button"
              onClick={() => onChange(value as PresenceFilterValue)}
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                px: '12px',
                py: '6px',
                fontSize: 13,
                fontWeight: 700,
                lineHeight: '20px',
                cursor: 'pointer',
                border: '1px solid',
                borderColor: 'primary.main',
                borderLeft: isFirst ? '1px solid' : 'none',
                borderRight: isLast ? '1px solid' : 'none',
                borderRadius: isFirst
                  ? '999px 0 0 999px'
                  : isLast
                    ? '0 999px 999px 0'
                    : 0,
                bgcolor: isSelected ? 'primary.main' : 'transparent',
                color: isSelected ? '#fff' : 'primary.main',
                whiteSpace: 'nowrap',
                '&:hover': {
                  bgcolor: isSelected
                    ? 'primary.dark'
                    : theme => `${theme.palette.primary.main}0f`,
                },
              }}
            >
              {tabLabel}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}

interface ActivityPresenceFiltersSectionProps {
  values: ActivityPresenceFilters;
  onChange: (next: ActivityPresenceFilters) => void;
  showReviews?: boolean;
}

export default function ActivityPresenceFiltersSection({
  values,
  onChange,
  showReviews = false,
}: ActivityPresenceFiltersSectionProps) {
  const setField = (
    field: keyof ActivityPresenceFilters,
    value: PresenceFilterValue
  ) => {
    onChange({ ...values, [field]: value });
  };

  return (
    <FilterSection title="Activity">
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <PresenceFilterRow
          label="Tags"
          tabs={[...PRESENCE_OPTIONS]}
          activeValue={values.tags}
          onChange={value => setField('tags', value)}
        />
        {showReviews && (
          <PresenceFilterRow
            label="Reviews"
            tabs={[...PRESENCE_OPTIONS]}
            activeValue={values.reviews ?? 'all'}
            onChange={value => setField('reviews', value)}
          />
        )}
        <PresenceFilterRow
          label="Comments"
          tabs={[...PRESENCE_OPTIONS]}
          activeValue={values.comments}
          onChange={value => setField('comments', value)}
        />
        <PresenceFilterRow
          label="Tasks"
          tabs={[...PRESENCE_OPTIONS]}
          activeValue={values.tasks}
          onChange={value => setField('tasks', value)}
        />
      </Box>
    </FilterSection>
  );
}
