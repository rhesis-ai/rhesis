'use client';

import React from 'react';
import Box from '@mui/material/Box';
import { SxProps, Theme } from '@mui/material/styles';
import { FilterButton } from '@/components/common/FilterButton';
import { SearchPill } from '@/components/common/SearchPill';
import { BORDER_RADIUS } from '@/styles/theme';

export interface ToolbarPillTab {
  label: string;
  value: string;
  icon?: React.ReactNode;
}

export interface GridToolbarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  searchWidth?: number;
  /** Use `standalone` on directory pages where the toolbar sits on the page bg. */
  searchVariant?: 'embedded' | 'standalone';
  onFilterClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  hasActiveFilters?: boolean;
  /** Number of active filters to display on the filter button badge */
  activeFilterCount?: number;
  middleContent?: React.ReactNode;
  rightContent?: React.ReactNode;
  sx?: SxProps<Theme>;
}

/** Toolbar row styling for card-directory pages (no grid border). */
export const directoryToolbarSx: SxProps<Theme> = {
  mb: 3,
  px: 0,
  py: 0,
  borderBottom: 'none',
  minHeight: 'auto',
};

/** Spread on directory toolbars: layout + raised search pill for page-bg contrast. */
export const directoryToolbarProps = {
  sx: directoryToolbarSx,
  searchVariant: 'standalone',
} as const satisfies Pick<GridToolbarProps, 'sx' | 'searchVariant'>;

export interface PrimarySegmentedPillsProps {
  tabs: ToolbarPillTab[];
  mode: 'single' | 'multi';
  activeValue?: string;
  selectedValues?: string[];
  onSingleChange?: (value: string) => void;
  onMultiChange?: (values: string[]) => void;
  /** Tab value that clears multi-select (e.g. "All"). */
  clearValue?: string;
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
    <PrimarySegmentedPills
      tabs={tabs}
      mode="single"
      activeValue={activeValue}
      onSingleChange={onChange}
    />
  );
}

/** Primary-bordered segmented pills for directory pages (single or multi-select). */
export function PrimarySegmentedPills({
  tabs,
  mode,
  activeValue = '',
  selectedValues = [],
  onSingleChange,
  onMultiChange,
  clearValue = '',
}: PrimarySegmentedPillsProps) {
  return (
    <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
      {tabs.map(({ value, label, icon }, idx, arr) => {
        const isSelected =
          mode === 'single'
            ? activeValue === value
            : value === clearValue
              ? selectedValues.length === 0
              : selectedValues.includes(value);
        const isFirst = idx === 0;
        const isLast = idx === arr.length - 1;

        return (
          <Box
            key={value || 'all'}
            component="button"
            type="button"
            onClick={() => {
              if (mode === 'single') {
                onSingleChange?.(value);
                return;
              }
              if (value === clearValue) {
                onMultiChange?.([]);
                return;
              }
              const next = selectedValues.includes(value)
                ? selectedValues.filter(v => v !== value)
                : [...selectedValues, value];
              onMultiChange?.(next);
            }}
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              px: '16px',
              py: '8px',
              fontSize: 14,
              fontWeight: 700,
              lineHeight: '22px',
              cursor: 'pointer',
              border: '1px solid',
              borderColor: 'primary.main',
              borderLeft: isFirst ? '1px solid' : 'none',
              borderRight: isLast ? '1px solid' : 'none',
              borderRadius: isFirst
                ? `${BORDER_RADIUS.pill} 0 0 ${BORDER_RADIUS.pill}`
                : isLast
                  ? `0 ${BORDER_RADIUS.pill} ${BORDER_RADIUS.pill} 0`
                  : 0,
              bgcolor: isSelected ? 'primary.main' : 'transparent',
              color: isSelected ? '#fff' : 'primary.main',
              transition: 'background-color 0.15s, color 0.15s',
              '&:hover': {
                bgcolor: isSelected
                  ? 'primary.dark'
                  : theme => `${theme.palette.primary.main}0f`,
              },
              whiteSpace: 'nowrap',
              '& svg': {
                fontSize: 20,
              },
            }}
          >
            {icon}
            {label}
          </Box>
        );
      })}
    </Box>
  );
}

/** Toolbar row inside a linked-data card (Figma 1435:46915) — below a card header. */
export const linkedGridToolbarSx: SxProps<Theme> = {
  px: '30px',
  pt: 0,
  pb: '30px',
  minHeight: 'auto',
  borderBottom: 'none',
};

/** Bleed a grid to SectionCard edges so toolbar/columns/footer share one 30px inset. */
export const sectionCardGridBleedSx: SxProps<Theme> = {
  mx: '-30px',
  width: 'calc(100% + 60px)',
};

/** 48px row/header height matching Figma linked-data table rows. */
export const linkedDataGridRowSx: SxProps<Theme> = {
  '& .MuiDataGrid-columnHeaders': {
    minHeight: '48px !important',
    maxHeight: '48px !important',
  },
  '& .MuiDataGrid-columnHeader': {
    minHeight: '48px !important',
    maxHeight: '48px !important',
  },
  '& .MuiDataGrid-row': {
    minHeight: '48px !important',
    maxHeight: '48px !important',
  },
  '& .MuiDataGrid-cell': {
    minHeight: '48px !important',
    maxHeight: '48px !important',
    fontSize: 14,
    lineHeight: '22px',
  },
  '& .MuiDataGrid-columnHeaderTitle': {
    fontSize: 14,
    lineHeight: '22px',
  },
};

/**
 * Shared toolbar row for BaseDataGrid: filter button, search pill, optional middle/right slots.
 */
export function GridToolbar({
  searchQuery,
  onSearchChange,
  searchPlaceholder = 'Search…',
  searchWidth = 240,
  searchVariant = 'embedded',
  onFilterClick,
  hasActiveFilters = false,
  activeFilterCount,
  middleContent,
  rightContent,
  sx,
}: GridToolbarProps) {
  // Figma grid-card default: 30px all around. Directory pages and drawers
  // that render the toolbar outside a grid border override px/py via `sx`
  // (e.g. `directoryToolbarSx`).
  const baseSx: SxProps<Theme> = {
    display: 'flex',
    alignItems: 'center',
    gap: 1.5,
    px: '30px',
    py: '30px',
    minHeight: 52,
  };

  return (
    <Box sx={[baseSx, ...(Array.isArray(sx) ? sx : sx ? [sx] : [])]}>
      {onFilterClick ? (
        <FilterButton
          onClick={onFilterClick}
          hasActiveFilters={hasActiveFilters}
          activeFilterCount={activeFilterCount}
        />
      ) : null}
      <SearchPill
        value={searchQuery}
        onChange={onSearchChange}
        placeholder={searchPlaceholder}
        width={searchWidth}
        variant={searchVariant}
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
