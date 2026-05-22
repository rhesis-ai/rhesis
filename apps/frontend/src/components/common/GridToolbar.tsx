'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ButtonGroup from '@mui/material/ButtonGroup';
import { SxProps, Theme, useTheme } from '@mui/material/styles';
import { FilterButton } from '@/components/common/FilterButton';
import { SearchPill } from '@/components/common/SearchPill';
import { BORDER_RADIUS, GREYSCALE } from '@/styles/theme';

export interface ToolbarPillTab {
  label: string;
  value: string;
}

export interface GridToolbarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  searchWidth?: number;
  onFilterClick: () => void;
  hasActiveFilters?: boolean;
  middleContent?: React.ReactNode;
  rightContent?: React.ReactNode;
  sx?: SxProps<Theme>;
}

export interface ToolbarPillTabsProps {
  tabs: ToolbarPillTab[];
  activeValue: string;
  onChange: (value: string) => void;
}

/** Centered segmented pill tabs used in grid toolbars (type/status filters). */
export function ToolbarPillTabs({
  tabs,
  activeValue,
  onChange,
}: ToolbarPillTabsProps) {
  return (
    <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
      <ButtonGroup
        variant="outlined"
        size="small"
        sx={{
          '& .MuiButtonGroup-grouped': {
            borderRadius: 0,
            '&:first-of-type': {
              borderTopLeftRadius: BORDER_RADIUS.pill,
              borderBottomLeftRadius: BORDER_RADIUS.pill,
            },
            '&:last-of-type': {
              borderTopRightRadius: BORDER_RADIUS.pill,
              borderBottomRightRadius: BORDER_RADIUS.pill,
            },
            borderColor: theme =>
              theme.palette.mode === 'light'
                ? GREYSCALE.light.border
                : GREYSCALE.dark.border,
          },
        }}
      >
        {tabs.map(tab => (
          <Button
            key={tab.value}
            onClick={() => onChange(tab.value)}
            sx={{
              px: 2,
              py: 0.5,
              fontWeight: activeValue === tab.value ? 600 : 400,
              bgcolor:
                activeValue === tab.value ? 'primary.dark' : 'transparent',
              color:
                activeValue === tab.value
                  ? '#fff'
                  : theme =>
                      theme.palette.mode === 'light'
                        ? GREYSCALE.light.body
                        : GREYSCALE.dark.body,
              '&:hover': {
                bgcolor:
                  activeValue === tab.value
                    ? 'primary.dark'
                    : theme =>
                        theme.palette.mode === 'light'
                          ? GREYSCALE.light.surface1
                          : GREYSCALE.dark.surface1,
              },
            }}
          >
            {tab.label}
          </Button>
        ))}
      </ButtonGroup>
    </Box>
  );
}

/**
 * Shared toolbar row for BaseDataGrid: filter button, search pill, optional middle/right slots.
 */
export function GridToolbar({
  searchQuery,
  onSearchChange,
  searchPlaceholder = 'Search…',
  searchWidth = 240,
  onFilterClick,
  hasActiveFilters = false,
  middleContent,
  rightContent,
  sx,
}: GridToolbarProps) {
  const theme = useTheme();

  const baseSx: SxProps<Theme> = {
    display: 'flex',
    alignItems: 'center',
    gap: 1.5,
    px: 2,
    py: 1,
    borderBottom: `1px solid ${
      theme.palette.mode === 'light'
        ? GREYSCALE.light.border
        : GREYSCALE.dark.border
    }`,
    minHeight: 52,
  };

  return (
    <Box sx={[baseSx, ...(Array.isArray(sx) ? sx : sx ? [sx] : [])]}>
      <FilterButton
        onClick={onFilterClick}
        hasActiveFilters={hasActiveFilters}
      />
      <SearchPill
        value={searchQuery}
        onChange={onSearchChange}
        placeholder={searchPlaceholder}
        width={searchWidth}
      />
      {middleContent}
      {!middleContent && <Box sx={{ flex: 1 }} />}
      {rightContent ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {rightContent}
        </Box>
      ) : null}
    </Box>
  );
}

export default GridToolbar;
