'use client';

import React, { useCallback, useEffect, useState } from 'react';
import type {
  GridFilterModel,
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

export function useGridState({
  searchQuery = '',
  typeFilter,
  typeFilterField,
  applyDrawerFilters,
  initialPageSize = 25,
}: UseGridStateOptions = {}): UseGridStateResult {
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: initialPageSize,
  });
  const [sortModel, setSortModel] = useState<GridSortModel>(DEFAULT_GRID_SORT);

  // Sync searchQuery into filterModel
  useEffect(() => {
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => item.field !== 'quickFilter'
      );
      const newItem = searchQuery
        ? { field: 'quickFilter', operator: 'contains', value: searchQuery }
        : null;
      const items = newItem ? [...otherItems, newItem] : otherItems;
      if (
        items.length === prev.items.length &&
        items.every(
          (it, i) => JSON.stringify(it) === JSON.stringify(prev.items[i])
        )
      )
        return prev;
      return { ...prev, items };
    });
    setPaginationModel(prev => (prev.page === 0 ? prev : { ...prev, page: 0 }));
  }, [searchQuery]);

  // Sync typeFilter pill tab into filterModel
  useEffect(() => {
    if (!typeFilterField) return;
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => item.field !== typeFilterField
      );
      const newItem =
        typeFilter && typeFilter !== 'all'
          ? { field: typeFilterField, operator: 'equals', value: typeFilter }
          : null;
      const items = newItem ? [...otherItems, newItem] : otherItems;
      if (
        items.length === prev.items.length &&
        items.every(
          (it, i) => JSON.stringify(it) === JSON.stringify(prev.items[i])
        )
      )
        return prev;
      return { ...prev, items };
    });
    setPaginationModel(prev => (prev.page === 0 ? prev : { ...prev, page: 0 }));
  }, [typeFilter, typeFilterField]);

  // Sync drawer filters into filterModel
  useEffect(() => {
    if (!applyDrawerFilters) return;
    setFilterModel(prev => {
      const next = applyDrawerFilters(prev);
      return next === prev || JSON.stringify(next) === JSON.stringify(prev)
        ? prev
        : next;
    });
    setPaginationModel(prev => (prev.page === 0 ? prev : { ...prev, page: 0 }));
    // applyDrawerFilters is a new function reference each render when drawerFilters changes,
    // so depending on it here is the correct way to react to drawer filter changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applyDrawerFilters]);

  const handlePaginationModelChange = useCallback(
    (model: GridPaginationModel) => {
      setPaginationModel(model);
    },
    []
  );

  const handleFilterModelChange = useCallback((model: GridFilterModel) => {
    setFilterModel(model);
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, []);

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
