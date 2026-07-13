'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type {
  GridFilterModel,
  GridFilterItem,
  GridPaginationModel,
  GridSortModel,
} from '@mui/x-data-grid';
import { DEFAULT_GRID_SORT } from '@/utils/grid-sort';

export interface UseGridStateOptions {
  searchQuery?: string;
  typeFilter?: string;
  typeFilterField?: string;
  applyDrawerFilters?: (prev: GridFilterModel) => GridFilterModel;
  /** Initial rows-per-page. Defaults to 25; pass each grid's prior default. */
  initialPageSize?: number;
}

export interface UseGridStateResult {
  filterModel: GridFilterModel;
  paginationModel: GridPaginationModel;
  sortModel: GridSortModel;
  setFilterModel: (model: GridFilterModel) => void;
  setPaginationModel: React.Dispatch<React.SetStateAction<GridPaginationModel>>;
  handlePaginationModelChange: (model: GridPaginationModel) => void;
  handleFilterModelChange: (model: GridFilterModel) => void;
  handleSortModelChange: (model: GridSortModel) => void;
}

const QUICK_FILTER_FIELDS = new Set(['quickFilter', '__quickFilter__']);

function isQuickFilterItem(item: GridFilterItem): boolean {
  return QUICK_FILTER_FIELDS.has(item.field ?? '');
}

function buildManagedFilterModel(
  searchQuery: string,
  typeFilter: string | undefined,
  typeFilterField: string | undefined,
  applyDrawerFilters: ((prev: GridFilterModel) => GridFilterModel) | undefined
): GridFilterModel {
  let model: GridFilterModel = { items: [] };

  if (searchQuery) {
    model = {
      ...model,
      items: [
        ...model.items,
        { field: 'quickFilter', operator: 'contains', value: searchQuery },
      ],
    };
  }

  if (applyDrawerFilters) {
    model = applyDrawerFilters(model);
  }

  // Apply pill-tab type filter after drawer filters so drawer helpers that
  // strip test_type.type_value do not remove an active toolbar tab selection.
  if (typeFilterField && typeFilter && typeFilter !== 'all') {
    model = {
      ...model,
      items: [
        ...model.items.filter(item => item.field !== typeFilterField),
        { field: typeFilterField, operator: 'equals', value: typeFilter },
      ],
    };
  }

  return model;
}

export function useGridState({
  searchQuery = '',
  typeFilter,
  typeFilterField,
  applyDrawerFilters,
  initialPageSize = 25,
}: UseGridStateOptions = {}): UseGridStateResult {
  const [columnFilterItems, setColumnFilterItems] = useState<GridFilterItem[]>(
    []
  );
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: initialPageSize,
  });
  const [sortModel, setSortModel] = useState<GridSortModel>(DEFAULT_GRID_SORT);

  const managedFilterModel = useMemo(
    () =>
      buildManagedFilterModel(
        searchQuery,
        typeFilter,
        typeFilterField,
        applyDrawerFilters
      ),
    [searchQuery, typeFilter, typeFilterField, applyDrawerFilters]
  );

  const filterModel = useMemo(
    () => ({
      items: [...managedFilterModel.items, ...columnFilterItems],
    }),
    [managedFilterModel, columnFilterItems]
  );

  useEffect(() => {
    setPaginationModel(prev => (prev.page === 0 ? prev : { ...prev, page: 0 }));
  }, [managedFilterModel]);

  const handlePaginationModelChange = useCallback(
    (model: GridPaginationModel) => {
      setPaginationModel(model);
    },
    []
  );

  const handleFilterModelChange = useCallback(
    (model: GridFilterModel) => {
      const managedFields = new Set(
        managedFilterModel.items
          .map(item => item.field)
          .filter((field): field is string => !!field)
      );

      const columnItems = model.items.filter(
        item =>
          item.field &&
          !managedFields.has(item.field) &&
          !isQuickFilterItem(item)
      );

      setColumnFilterItems(columnItems);
      setPaginationModel(prev => ({ ...prev, page: 0 }));
    },
    [managedFilterModel]
  );

  const setFilterModel = useCallback(
    (model: GridFilterModel) => {
      handleFilterModelChange(model);
    },
    [handleFilterModelChange]
  );

  const handleSortModelChange = useCallback((model: GridSortModel) => {
    setSortModel(model);
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, []);

  return {
    filterModel,
    paginationModel,
    sortModel,
    setFilterModel,
    setPaginationModel,
    handlePaginationModelChange,
    handleFilterModelChange,
    handleSortModelChange,
  };
}
