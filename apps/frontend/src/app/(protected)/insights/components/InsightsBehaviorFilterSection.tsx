'use client';

import * as React from 'react';
import {
  Box,
  Checkbox,
  FormControlLabel,
  Link,
  Typography,
} from '@mui/material';
import { FilterSection } from '@/components/common/FilterDrawer';
import { InsightsBehaviorOption } from '../utils/insights-filter-utils';

const DEFAULT_VISIBLE_COUNT = 5;

interface InsightsBehaviorFilterSectionProps {
  options: InsightsBehaviorOption[];
  checkedIds: string[];
  onCheckedIdsChange: (ids: string[]) => void;
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
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
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
            <Box
              key={option.id}
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                minHeight: 38,
              }}
            >
              <FormControlLabel
                control={
                  <Checkbox
                    checked={checkedIds.includes(option.id)}
                    onChange={() => toggleBehavior(option.id)}
                    size="small"
                    sx={{ py: 0.75 }}
                  />
                }
                label={
                  <Typography
                    sx={{
                      fontSize: 14,
                      lineHeight: '22px',
                      color: theme => theme.palette.greyscale.title,
                    }}
                  >
                    {option.name}
                  </Typography>
                }
                sx={{ ml: 0, mr: 0, flex: 1, minWidth: 0 }}
              />
              <Typography
                sx={{
                  fontSize: 14,
                  lineHeight: '22px',
                  color: theme => theme.palette.greyscale.subtitle,
                  flexShrink: 0,
                  pl: 1,
                }}
              >
                {option.count}
              </Typography>
            </Box>
          ))}
        </Box>

        <Typography
          sx={{
            fontSize: 12,
            lineHeight: '18px',
            color: 'text.secondary',
            pt: 0.25,
          }}
        >
          Uncheck behaviors to hide them from the pass rate view.
        </Typography>

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
            }}
          >
            Show all
          </Link>
        ) : null}
      </Box>
    </FilterSection>
  );
}
