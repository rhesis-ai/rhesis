'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';

export interface ProjectFilters {
  activeStatus: boolean | null;
  environments: string[];
}

export const EMPTY_FILTERS: ProjectFilters = {
  activeStatus: null,
  environments: [],
};

export function hasActiveProjectFilters(f: ProjectFilters): boolean {
  return f.activeStatus !== null || f.environments.length > 0;
}

export function countActiveProjectFilters(f: ProjectFilters): number {
  return (f.activeStatus !== null ? 1 : 0) + f.environments.length;
}

const ENVIRONMENTS = ['development', 'staging', 'production'] as const;
const ENV_LABELS: Record<string, string> = {
  development: 'Development',
  staging: 'Staging',
  production: 'Production',
};

interface ProjectFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: ProjectFilters;
  onApply: (filters: ProjectFilters) => void;
}

export default function ProjectFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: ProjectFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_FILTERS,
    onApply,
    onClose
  );

  const toggleEnvironment = (env: string) => {
    setDraft(prev => ({
      ...prev,
      environments: prev.environments.includes(env)
        ? prev.environments.filter(e => e !== env)
        : [...prev.environments, env],
    }));
  };

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Status">
        <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {[
            { label: 'Active', value: true as const },
            { label: 'Inactive', value: false as const },
          ].map(({ label, value }) => (
            <Box
              key={label}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  activeStatus: prev.activeStatus === value ? null : value,
                }))
              }
              sx={filterChipSx(draft.activeStatus === value)}
            >
              {label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Environment">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {ENVIRONMENTS.map(env => (
            <Box
              key={env}
              component="button"
              onClick={() => toggleEnvironment(env)}
              sx={filterChipSx(draft.environments.includes(env))}
            >
              {ENV_LABELS[env]}
            </Box>
          ))}
        </Box>
      </FilterSection>
    </FilterDrawerShell>
  );
}
