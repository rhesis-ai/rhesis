'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';

export interface LinkedFilterOption {
  value: string;
  label: string;
}

export interface LinkedFilterSectionConfig {
  key: string;
  title: string;
  options: LinkedFilterOption[];
}

export type LinkedFilterValues = Record<string, string[]>;

export function emptyLinkedFilters(
  sections: LinkedFilterSectionConfig[]
): LinkedFilterValues {
  return sections.reduce<LinkedFilterValues>((acc, section) => {
    acc[section.key] = [];
    return acc;
  }, {});
}

export function hasActiveLinkedFilters(filters: LinkedFilterValues): boolean {
  return Object.values(filters).some(values => values.length > 0);
}

export function countActiveLinkedFilters(filters: LinkedFilterValues): number {
  return Object.values(filters).reduce(
    (total, values) => total + values.length,
    0
  );
}

interface LinkedEntitiesFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  sections: LinkedFilterSectionConfig[];
  filters: LinkedFilterValues;
  onApply: (filters: LinkedFilterValues) => void;
}

/**
 * Client-side filter drawer for linked-entity grids. Renders one chip section
 * per provided config and returns the selected values map on apply.
 */
export default function LinkedEntitiesFilterDrawer({
  open,
  onClose,
  sections,
  filters,
  onApply,
}: LinkedEntitiesFilterDrawerProps) {
  const empty = React.useMemo(() => emptyLinkedFilters(sections), [sections]);

  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    empty,
    onApply,
    onClose
  );

  const toggle = (key: string, value: string) => {
    setDraft(prev => {
      const arr = prev[key] ?? [];
      return {
        ...prev,
        [key]: arr.includes(value)
          ? arr.filter(v => v !== value)
          : [...arr, value],
      };
    });
  };

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      {sections
        .filter(section => section.options.length > 0)
        .map(section => (
          <FilterSection key={section.key} title={section.title}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {section.options.map(option => (
                <Box
                  key={option.value}
                  component="button"
                  onClick={() => toggle(section.key, option.value)}
                  sx={filterChipSx(
                    (draft[section.key] ?? []).includes(option.value)
                  )}
                >
                  {option.label}
                </Box>
              ))}
            </Box>
          </FilterSection>
        ))}
    </FilterDrawerShell>
  );
}
