import { act, renderHook } from '@testing-library/react';
import { GridLogicOperator, type GridFilterModel } from '@mui/x-data-grid';
import { useGridState } from '../useGridState';
import { applyTestDrawerFiltersToModel } from '@/app/(protected)/tests/components/test-filter-model';
import { EMPTY_TEST_FILTERS } from '@/app/(protected)/tests/components/TestFilterDrawer';
import { combineTestFiltersToOData } from '@/utils/odata-filter';

describe('useGridState', () => {
  it('keeps search when drawer filters are applied first', () => {
    const drawerFilters = { ...EMPTY_TEST_FILTERS, behavior: 'Active' };

    const { result, rerender } = renderHook(
      ({
        searchQuery,
        drawerFilters: filters,
      }: {
        searchQuery: string;
        drawerFilters: typeof EMPTY_TEST_FILTERS;
      }) =>
        useGridState({
          searchQuery,
          applyDrawerFilters: (prev: GridFilterModel) =>
            applyTestDrawerFiltersToModel(prev, filters),
        }),
      {
        initialProps: {
          searchQuery: '',
          drawerFilters,
        },
      }
    );

    expect(result.current.filterModel.items).toEqual([
      {
        id: 'behavior.name',
        field: 'behavior.name',
        operator: 'equals',
        value: 'Active',
      },
    ]);

    rerender({ searchQuery: 'refund', drawerFilters });

    expect(result.current.filterModel.items).toEqual(
      expect.arrayContaining([
        {
          id: 'quickFilter',
          field: 'quickFilter',
          operator: 'contains',
          value: 'refund',
        },
        {
          id: 'behavior.name',
          field: 'behavior.name',
          operator: 'equals',
          value: 'Active',
        },
      ])
    );
  });

  it('preserves toolbar search when DataGrid echoes a stripped filter model', () => {
    const drawerFilters = { ...EMPTY_TEST_FILTERS, behavior: 'Safety' };

    const { result } = renderHook(() =>
      useGridState({
        searchQuery: 'prompt text',
        applyDrawerFilters: (prev: GridFilterModel) =>
          applyTestDrawerFiltersToModel(prev, drawerFilters),
      })
    );

    act(() => {
      result.current.handleFilterModelChange({
        items: [
          {
            field: 'behavior.name',
            operator: 'equals',
            value: 'Safety',
          },
        ],
      });
    });

    expect(result.current.filterModel.items).toEqual(
      expect.arrayContaining([
        {
          id: 'quickFilter',
          field: 'quickFilter',
          operator: 'contains',
          value: 'prompt text',
        },
        {
          id: 'behavior.name',
          field: 'behavior.name',
          operator: 'equals',
          value: 'Safety',
        },
      ])
    );
  });

  it('combines type pill, drawer, and search filters atomically', () => {
    const drawerFilters = { ...EMPTY_TEST_FILTERS, topic: 'Billing' };

    const { result } = renderHook(() =>
      useGridState({
        searchQuery: 'invoice',
        typeFilter: 'Single-Turn',
        typeFilterField: 'test_type.type_value',
        applyDrawerFilters: (prev: GridFilterModel) =>
          applyTestDrawerFiltersToModel(prev, drawerFilters),
      })
    );

    expect(result.current.filterModel.items).toEqual(
      expect.arrayContaining([
        {
          id: 'quickFilter',
          field: 'quickFilter',
          operator: 'contains',
          value: 'invoice',
        },
        {
          id: 'test_type.type_value',
          field: 'test_type.type_value',
          operator: 'equals',
          value: 'Single-Turn',
        },
        {
          id: 'topic.name',
          field: 'topic.name',
          operator: 'equals',
          value: 'Billing',
        },
      ])
    );
  });

  it('drops stale column filters when the same field becomes toolbar-managed', () => {
    const drawerFilters = { ...EMPTY_TEST_FILTERS, behavior: 'Active' };

    const { result, rerender } = renderHook(
      ({
        searchQuery,
        drawerFilters: filters,
      }: {
        searchQuery: string;
        drawerFilters: typeof EMPTY_TEST_FILTERS;
      }) =>
        useGridState({
          searchQuery,
          applyDrawerFilters: (prev: GridFilterModel) =>
            applyTestDrawerFiltersToModel(prev, filters),
        }),
      {
        initialProps: {
          searchQuery: '',
          drawerFilters: EMPTY_TEST_FILTERS,
        },
      }
    );

    act(() => {
      result.current.handleFilterModelChange({
        items: [
          {
            field: 'behavior.name',
            operator: 'equals',
            value: 'Draft',
          },
        ],
      });
    });

    expect(result.current.filterModel.items).toEqual([
      {
        field: 'behavior.name',
        operator: 'equals',
        value: 'Draft',
      },
    ]);

    rerender({ searchQuery: '', drawerFilters });

    expect(result.current.filterModel.items).toEqual([
      {
        id: 'behavior.name',
        field: 'behavior.name',
        operator: 'equals',
        value: 'Active',
      },
    ]);
  });

  it('forces AND logic when DataGrid echoes logicOperator or', () => {
    const drawerFilters = {
      ...EMPTY_TEST_FILTERS,
      behavior: 'Accuracy Testing',
      category: 'New',
    };

    const { result } = renderHook(() =>
      useGridState({
        applyDrawerFilters: (prev: GridFilterModel) =>
          applyTestDrawerFiltersToModel(prev, drawerFilters),
      })
    );

    act(() => {
      result.current.handleFilterModelChange({
        logicOperator: GridLogicOperator.Or,
        items: [
          {
            field: 'behavior.name',
            operator: 'equals',
            value: 'Accuracy Testing',
          },
        ],
      });
    });

    expect(result.current.filterModel.logicOperator).toBe(
      GridLogicOperator.And
    );

    const odata = combineTestFiltersToOData(result.current.filterModel);
    expect(odata).toContain(' and ');
    expect(odata).not.toMatch(/\bor\b/);
  });
});
