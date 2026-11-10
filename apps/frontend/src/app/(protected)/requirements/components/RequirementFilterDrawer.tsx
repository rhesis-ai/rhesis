'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import RequirementAutocomplete from '@/components/requirements/RequirementAutocomplete';
import type { RequirementOption } from '@/utils/api-client/interfaces/requirement';
import { useRequirementImpacts } from './requirement-lookups';

export type MetricFilter = 'all' | 'has_metrics' | 'no_metrics';
export type HierarchyFilter = 'all' | 'top_level' | 'has_parent';

export interface RequirementFilters {
  metricCount: MetricFilter;
  tagNames: string[];
  impactIds: string[];
  hierarchy: HierarchyFilter;
  /** Only children of this requirement. Wins over `hierarchy`. */
  parent: RequirementOption | null;
}

export const EMPTY_REQUIREMENT_FILTERS: RequirementFilters = {
  metricCount: 'all',
  tagNames: [],
  impactIds: [],
  hierarchy: 'all',
  parent: null,
};

export function countActiveRequirementFilters(f: RequirementFilters): number {
  return (
    (f.metricCount !== 'all' ? 1 : 0) +
    f.tagNames.length +
    f.impactIds.length +
    (f.parent || f.hierarchy !== 'all' ? 1 : 0)
  );
}

export function hasActiveRequirementFilters(f: RequirementFilters): boolean {
  return countActiveRequirementFilters(f) > 0;
}

/** The list's `hierarchy` filter value for the drawer state. */
export function hierarchyFilterValue(f: RequirementFilters): string {
  return f.parent ? String(f.parent.id) : f.hierarchy;
}

const HIERARCHY_OPTIONS: { value: HierarchyFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'top_level', label: 'Top-level only' },
  { value: 'has_parent', label: 'Has a parent' },
];

function toggle(list: string[], value: string): string[] {
  return list.includes(value)
    ? list.filter(v => v !== value)
    : [...list, value];
}

const METRIC_OPTIONS: { value: MetricFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'has_metrics', label: 'Has Metrics' },
  { value: 'no_metrics', label: 'No Metrics' },
];

interface RequirementFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: RequirementFilters;
  /** Unique tag names available across the loaded requirements. */
  availableTagNames?: string[];
  onApply: (filters: RequirementFilters) => void;
}

export default function RequirementFilterDrawer({
  open,
  onClose,
  filters,
  availableTagNames = [],
  onApply,
}: RequirementFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_REQUIREMENT_FILTERS,
    onApply,
    onClose
  );

  const { data: impactOptions = [] } = useRequirementImpacts(open);

  const toggleTag = (name: string) => {
    setDraft(prev => ({ ...prev, tagNames: toggle(prev.tagNames, name) }));
  };

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Metrics">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {METRIC_OPTIONS.map(({ value, label }) => (
            <Box
              key={value}
              component="button"
              onClick={() =>
                setDraft(prev => ({ ...prev, metricCount: value }))
              }
              sx={filterChipSx(draft.metricCount === value)}
            >
              {label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Impact">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {impactOptions.map(option => (
            <Box
              key={option.id}
              component="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  impactIds: toggle(prev.impactIds, String(option.id)),
                }))
              }
              sx={filterChipSx(draft.impactIds.includes(String(option.id)))}
            >
              {option.type_value}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Parent">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
          {HIERARCHY_OPTIONS.map(({ value, label }) => (
            <Box
              key={value}
              component="button"
              onClick={() =>
                setDraft(prev => ({ ...prev, hierarchy: value, parent: null }))
              }
              sx={filterChipSx(!draft.parent && draft.hierarchy === value)}
            >
              {label}
            </Box>
          ))}
        </Box>
        <RequirementAutocomplete
          label="Children of"
          topLevelOnly
          value={draft.parent}
          onChange={parent =>
            setDraft(prev => ({ ...prev, parent, hierarchy: 'all' }))
          }
        />
      </FilterSection>

      <FilterSection title="Tags">
        {availableTagNames.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No tags yet. Add tags from the requirement edit drawer to group your
            requirements.
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {availableTagNames.map(name => (
              <Box
                key={name}
                component="button"
                onClick={() => toggleTag(name)}
                sx={filterChipSx(draft.tagNames.includes(name))}
              >
                {name}
              </Box>
            ))}
          </Box>
        )}
      </FilterSection>
    </FilterDrawerShell>
  );
}
