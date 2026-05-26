'use client';

import * as React from 'react';
import { Box, Switch, Typography } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
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
  const [draft, setDraft] = React.useState<ProjectFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const toggleEnvironment = (env: string) => {
    setDraft(prev => ({
      ...prev,
      environments: prev.environments.includes(env)
        ? prev.environments.filter(e => e !== env)
        : [...prev.environments, env],
    }));
  };

  const handleReset = () => setDraft(EMPTY_FILTERS);

  const handleApply = () => {
    onApply(draft);
    onClose();
  };

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Status">
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {[
            { label: 'Active', value: true as const },
            { label: 'Inactive', value: false as const },
          ].map(({ label, value }) => (
            <Box
              key={label}
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                height: 38,
              }}
            >
              <Typography
                sx={{
                  fontSize: 14,
                  color: theme => theme.palette.greyscale.body,
                }}
              >
                {label}
              </Typography>
              <Switch
                checked={draft.activeStatus === value}
                onChange={e => {
                  setDraft(prev => ({
                    ...prev,
                    activeStatus: e.target.checked ? value : null,
                  }));
                }}
                size="small"
                sx={{
                  '& .MuiSwitch-switchBase.Mui-checked': {
                    color: 'primary.main',
                  },
                  '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                    bgcolor: 'primary.main',
                  },
                }}
              />
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
