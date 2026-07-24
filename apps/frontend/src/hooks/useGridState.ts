'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  GridLogicOperator,
  type GridFilterModel,
  type GridFilterItem,
  type GridPaginationModel,
  type GridSortModel,
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
  /**
   * Community `DataGrid` hard-forces `disableMultipleColumnsFiltering: true`
   * (see `DATA_GRID_FORCED_PROPS` in `@mui/x-data-grid`), so it silently
   * truncates any controlled `filterModel` with 2+ items on every render. If
   * the truncated result differs from the (still multi-item) controlled
   * prop, DataGrid treats that as a prop change and re-fires
   * `onFilterModelChange`, which — with our multi-item managed/drawer
   * filters — creates an infinite `setState` loop (React error 185). Pass
   * this pre-truncated, single-item-safe model to the `<DataGrid>`
   * component's `filterModel` prop instead of `filterModel`. Use the full
   * `filterModel` only for building the server-side filter query, since
   * actual row filtering happens server-side, not in the grid.
   */
  gridFilterModel: GridFilterModel;
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

function getManagedFilterFields(model: GridFilterModel): Set<string> {
  return new Set(
    model.items
      .map(item => item.field)
      .filter((field): field is string => !!field)
  );
}

function stripManagedColumnItems(
  columnItems: GridFilterItem[],
  managedFields: Set<string>
): GridFilterItem[] {
  return columnItems.filter(
    item =>
      item.field && !managedFields.has(item.field) && !isQuickFilterItem(item)
  );
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
        {
          id: 'quickFilter',
          field: 'quickFilter',
          operator: 'contains',
          value: searchQuery,
        },
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
        {
          id: typeFilterField,
          field: typeFilterField,
          operator: 'equals',
          value: typeFilter,
        },
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
  const [gridFilterMeta, setGridFilterMeta] = useState<
    Pick<
      GridFilterModel,
      'logicOperator' | 'quickFilterValues' | 'quickFilterLogicOperator'
    >
  >({});
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

  const managedFields = useMemo(
    () => getManagedFilterFields(managedFilterModel),
    [managedFilterModel]
  );

  const reconciledColumnFilterItems = useMemo(
    () => stripManagedColumnItems(columnFilterItems, managedFields),
    [columnFilterItems, managedFields]
  );

  const filterModel = useMemo(
    () => ({
      ...gridFilterMeta,
      // Drawer/toolbar filters must always combine with AND. DataGrid can echo
      // logicOperator: 'or', which would incorrectly broaden multi-filter results.
      logicOperator: GridLogicOperator.And,
      items: [...managedFilterModel.items, ...reconciledColumnFilterItems],
    }),
    [gridFilterMeta, managedFilterModel, reconciledColumnFilterItems]
  );

  const gridFilterModel = useMemo(() => {
    // Prefer a column-driven item (the DataGrid's own filter panel — see
    // `SortOnlyColumnMenu` in BaseDataGrid.tsx, which currently hides that
    // panel's entry point, but keep this correct in case it's re-enabled)
    // over a managed one, so a user-added column filter isn't silently
    // dropped just because a drawer/search/tab filter is also active.
    const items = reconciledColumnFilterItems.slice(0, 1);
    if (items.length === 0 && managedFilterModel.items.length > 0) {
      items.push(managedFilterModel.items[0]);
    }
    return { ...filterModel, items };
  }, [filterModel, reconciledColumnFilterItems, managedFilterModel]);

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
      const columnItems = stripManagedColumnItems(model.items, managedFields);

      setColumnFilterItems(columnItems);
      setGridFilterMeta(prev =>
        prev.logicOperator === model.logicOperator &&
        prev.quickFilterValues === model.quickFilterValues &&
        prev.quickFilterLogicOperator === model.quickFilterLogicOperator
          ? prev
          : {
              logicOperator: model.logicOperator,
              quickFilterValues: model.quickFilterValues,
              quickFilterLogicOperator: model.quickFilterLogicOperator,
            }
      );
      setPaginationModel(prev =>
        prev.page === 0 ? prev : { ...prev, page: 0 }
      );
    },
    [managedFields]
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
    gridFilterModel,
    paginationModel,
    sortModel,
    setFilterModel,
    setPaginationModel,
    handlePaginationModelChange,
    handleFilterModelChange,
    handleSortModelChange,
  };
}
