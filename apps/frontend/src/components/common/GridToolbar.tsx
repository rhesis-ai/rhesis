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
  /** When true, the search pill grows to fill remaining toolbar width. */
  searchFullWidth?: boolean;
  onFilterClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  hasActiveFilters?: boolean;
  /** Number of active filters to display on the filter button badge */
  activeFilterCount?: number;
  middleContent?: React.ReactNode;
  rightContent?: React.ReactNode;
  /** When false, hides the search pill (e.g. insights empty state toolbar). */
  showSearch?: boolean;
  sx?: SxProps<Theme>;
}

/** Toolbar row styling for card-directory pages (no grid border). */
export const directoryToolbarSx: SxProps<Theme> = {
  mb: 3,
  px: 0,
  py: 0,
  borderBottom: 'none',
  minHeight: 'auto',
  gap: '20px',
};

/** Spread on directory toolbars: layout + raised search pill for page-bg contrast. */
export const directoryToolbarProps = {
  sx: directoryToolbarSx,
  searchVariant: 'standalone',
  /** Figma Toolbar 841:38547 — Searchfield width */
  searchWidth: 288,
} as const satisfies Pick<
  GridToolbarProps,
  'sx' | 'searchVariant' | 'searchWidth'
>;

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
      <Box
        sx={{
          display: 'inline-flex',
          maxWidth: '100%',
          border: '1px solid',
          borderColor: 'primary.main',
          borderRadius: BORDER_RADIUS.pill,
          overflow: 'hidden',
        }}
      >
        {tabs.map(({ value, label, icon }, idx) => {
          const isSelected =
            mode === 'single'
              ? activeValue === value
              : value === clearValue
                ? selectedValues.length === 0
                : selectedValues.includes(value);

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
                border: 'none',
                borderRadius: 0,
                ...(idx > 0 && {
                  borderLeft: '1px solid',
                  borderColor: 'primary.main',
                }),
                bgcolor: isSelected ? 'primary.main' : 'transparent',
                color: isSelected ? '#fff' : 'primary.main',
                transition: 'background-color 0.15s, color 0.15s',
                outline: 'none',
                WebkitTapHighlightColor: 'transparent',
                '&:focus-visible': {
                  outline: '2px solid',
                  outlineColor: 'primary.main',
                  outlineOffset: -2,
                  zIndex: 1,
                },
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

/** Shared 30px horizontal inset for grids/tables embedded in a bleeded section card. */
export const SECTION_CARD_GRID_INSET_PX = '30px';

/** Table horizontal padding inside a bleeded section-card grid area. */
export const sectionCardGridTableInsetSx: SxProps<Theme> = {
  px: SECTION_CARD_GRID_INSET_PX,
};

/** Clears edge cell padding when the table container already provides horizontal inset. */
export const sectionCardGridTableEdgeCellResetSx: SxProps<Theme> = {
  '& .MuiTableCell-root:first-of-type': {
    pl: 0,
  },
  '& .MuiTableCell-root:last-of-type': {
    pr: 0,
  },
};

/** DataGrid column/footer horizontal inset inside a bleeded section-card grid area. */
export const sectionCardGridDataGridInsetSx: SxProps<Theme> = {
  '&& .MuiDataGrid-columnHeader--first': {
    paddingLeft: SECTION_CARD_GRID_INSET_PX,
  },
  '&& .MuiDataGrid-columnHeader--last': {
    paddingRight: SECTION_CARD_GRID_INSET_PX,
  },
  '&& .MuiDataGrid-cell:first-child': {
    paddingLeft: SECTION_CARD_GRID_INSET_PX,
  },
  '&& .MuiDataGrid-cell:last-of-type': {
    paddingRight: SECTION_CARD_GRID_INSET_PX,
  },
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
  searchFullWidth = false,
  onFilterClick,
  hasActiveFilters = false,
  activeFilterCount,
  middleContent,
  rightContent,
  showSearch = true,
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
      {showSearch ? (
        searchFullWidth ? (
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <SearchPill
              value={searchQuery}
              onChange={onSearchChange}
              placeholder={searchPlaceholder}
              width="100%"
              variant={searchVariant}
            />
          </Box>
        ) : (
          <SearchPill
            value={searchQuery}
            onChange={onSearchChange}
            placeholder={searchPlaceholder}
            width={searchWidth}
            variant={searchVariant}
          />
        )
      ) : null}
      {middleContent}
      {!middleContent && !searchFullWidth && showSearch && (
        <Box sx={{ flex: 1 }} />
      )}
      {!middleContent && !searchFullWidth && !showSearch && (
        <Box sx={{ flex: 1 }} />
      )}
      {rightContent ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {rightContent}
        </Box>
      ) : null}
    </Box>
  );
}

export default GridToolbar;
