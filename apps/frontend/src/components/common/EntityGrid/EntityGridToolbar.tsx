'use client';

import React, { createContext, useContext } from 'react';
import {
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import GridToolbar, {
  ToolbarPillTabs,
  type ToolbarPillTab,
} from '@/components/common/GridToolbar';
import SelectionModeToggle from '@/components/common/SelectionModeToggle';

/**
 * Everything the toolbar renders, provided by EntityGrid. A context is used
 * because BaseDataGrid's `toolbarSlot` receives no props — and the slot
 * component must be module-stable, or the DataGrid remounts the toolbar on
 * every render and the search input loses focus while typing.
 */
export interface EntityGridToolbarState {
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  searchPlaceholder: string;
  pills?: { tabs: ToolbarPillTab[] };
  pillValue: string;
  setPillValue: (value: string) => void;
  /** Undefined ⇒ no filter button. */
  openFilterDrawer?: () => void;
  hasActiveDrawerFilters: boolean;
  activeFilterCount: number;
  /** Undefined ⇒ no selection toggle (read-only or single-delete grids). */
  selection?: {
    checked: boolean;
    onChange: (checked: boolean) => void;
    label: string;
  };
  toolbarRight?: React.ReactNode;
  showGridButtons: boolean;
  showExport: boolean;
}

export const EntityGridToolbarContext = createContext<EntityGridToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  searchPlaceholder: 'Search…',
  pillValue: '',
  setPillValue: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
  showGridButtons: true,
  showExport: true,
});

/** The single toolbar slot every EntityGrid instance shares. */
export function EntityGridToolbarSlot() {
  const {
    searchQuery,
    setSearchQuery,
    searchPlaceholder,
    pills,
    pillValue,
    setPillValue,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
    selection,
    toolbarRight,
    showGridButtons,
    showExport,
  } = useContext(EntityGridToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder={searchPlaceholder}
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      activeFilterCount={activeFilterCount}
      middleContent={
        pills ? (
          <ToolbarPillTabs
            tabs={pills.tabs}
            activeValue={pillValue}
            onChange={setPillValue}
          />
        ) : undefined
      }
      rightContent={
        <>
          {selection && (
            <SelectionModeToggle
              checked={selection.checked}
              onChange={selection.onChange}
              label={selection.label}
            />
          )}
          {toolbarRight}
          {showGridButtons && (
            <>
              <GridToolbarColumnsButton />
              <GridToolbarDensitySelector />
              {showExport && <GridToolbarExport />}
            </>
          )}
        </>
      }
    />
  );
}
