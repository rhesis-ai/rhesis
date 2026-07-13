import { act, renderHook } from '@testing-library/react';
import type { GridFilterModel } from '@mui/x-data-grid';
import { useGridState } from '../useGridState';
import { applyTestDrawerFiltersToModel } from '@/app/(protected)/tests/components/test-filter-model';
import { EMPTY_TEST_FILTERS } from '@/app/(protected)/tests/components/TestFilterDrawer';

describe('useGridState', () => {
  it('keeps search when drawer filters are applied first', () => {
    const drawerFilters = { ...EMPTY_TEST_FILTERS, status: 'Active' };

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
        field: 'status.name',
        operator: 'contains',
        value: 'Active',
      },
    ]);

    rerender({ searchQuery: 'refund', drawerFilters });

    expect(result.current.filterModel.items).toEqual(
      expect.arrayContaining([
        {
          field: 'quickFilter',
          operator: 'contains',
          value: 'refund',
        },
        {
          field: 'status.name',
          operator: 'contains',
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
            operator: 'contains',
            value: 'Safety',
          },
        ],
      });
    });

    expect(result.current.filterModel.items).toEqual(
      expect.arrayContaining([
        {
          field: 'quickFilter',
          operator: 'contains',
          value: 'prompt text',
        },
        {
          field: 'behavior.name',
          operator: 'contains',
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
          field: 'quickFilter',
          operator: 'contains',
          value: 'invoice',
        },
        {
          field: 'test_type.type_value',
          operator: 'equals',
          value: 'Single-Turn',
        },
        {
          field: 'topic.name',
          operator: 'contains',
          value: 'Billing',
        },
      ])
    );
  });
});
