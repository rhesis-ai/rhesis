'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';

export interface MCPFilters {
  providers: string[];
}

export const EMPTY_MCP_FILTERS: MCPFilters = {
  providers: [],
};

export function hasActiveMCPFilters(f: MCPFilters): boolean {
  return f.providers.length > 0;
}

interface MCPFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: MCPFilters;
  availableProviders: string[];
  onApply: (filters: MCPFilters) => void;
}

export default function MCPFilterDrawer({
  open,
  onClose,
  filters,
  availableProviders,
  onApply,
}: MCPFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_MCP_FILTERS,
    onApply,
    onClose
  );

  const toggleProvider = (provider: string) => {
    setDraft(prev => ({
      ...prev,
      providers: prev.providers.includes(provider)
        ? prev.providers.filter(p => p !== provider)
        : [...prev.providers, provider],
    }));
  };

  const providerLabel = (p: string) =>
    p.charAt(0).toUpperCase() + p.slice(1).toLowerCase();

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      {availableProviders.length > 0 && (
        <FilterSection title="Provider">
          <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {availableProviders.map(provider => (
              <Box
                key={provider}
                component="button"
                onClick={() => toggleProvider(provider)}
                sx={filterChipSx(draft.providers.includes(provider))}
              >
                {providerLabel(provider)}
              </Box>
            ))}
          </Box>
        </FilterSection>
      )}
    </FilterDrawerShell>
  );
}
