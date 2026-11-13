'use client';

import * as React from 'react';
import { Box, Checkbox, Typography } from '@mui/material';
import { FilterSection } from '@/components/common/FilterDrawer';
import type { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import InsightsImpactDot from './InsightsImpactDot';

interface InsightsImpactFilterSectionProps {
  /** The organization's RequirementImpact lookups. */
  options: TypeLookup[];
  checkedIds: string[];
  onCheckedIdsChange: (ids: string[]) => void;
}

/**
 * Impact checkboxes, one per RequirementImpact lookup, with the dot colour
 * from the requirement cards. Same checked-means-shown semantics as the
 * requirement list: unchecking everything shows nothing.
 */
export default function InsightsImpactFilterSection({
  options,
  checkedIds,
  onCheckedIdsChange,
}: InsightsImpactFilterSectionProps) {
  if (options.length === 0) {
    return null;
  }

  const toggle = (id: string) => {
    onCheckedIdsChange(
      checkedIds.includes(id)
        ? checkedIds.filter(value => value !== id)
        : [...checkedIds, id]
    );
  };

  return (
    <FilterSection title="Impact">
      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
        {options.map(option => {
          const id = String(option.id);
          return (
            <Box
              key={id}
              sx={{ display: 'flex', alignItems: 'center', minWidth: 0 }}
            >
              <Checkbox
                checked={checkedIds.includes(id)}
                onChange={() => toggle(id)}
                sx={{ ml: -1 }}
                inputProps={{ 'aria-label': option.type_value }}
              />
              <InsightsImpactDot
                impact={option.type_value}
                sx={{ mr: 1, flexShrink: 0 }}
              />
              <Typography
                variant="body2"
                sx={{
                  color: theme => theme.palette.greyscale.title,
                  wordBreak: 'break-word',
                }}
              >
                {option.type_value}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </FilterSection>
  );
}
