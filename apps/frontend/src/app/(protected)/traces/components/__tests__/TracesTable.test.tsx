import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';

import TracesTable from '../TracesTable';
import { EMPTY_TRACE_DRAWER_FILTERS } from '../trace-filter-params';

// The filter drawer fetches on open; it stays closed here.
jest.mock('../TraceFilterDrawer', () => ({
  __esModule: true,
  default: () => null,
}));

describe('TracesTable toolbar', () => {
  it('has no turn-type pill tabs (the filter lives in the drawer)', async () => {
    render(
      <TracesTable
        traces={[]}
        loading={false}
        onRowClick={jest.fn()}
        totalCount={0}
        page={0}
        pageSize={50}
        onPageChange={jest.fn()}
        onPageSizeChange={jest.fn()}
        searchQuery=""
        onSearchQueryChange={jest.fn()}
        drawerFilters={EMPTY_TRACE_DRAWER_FILTERS}
        onApplyDrawerFilters={jest.fn()}
        filterDrawerOpen={false}
        onFilterDrawerOpen={jest.fn()}
        onFilterDrawerClose={jest.fn()}
      />
    );

    expect(
      await screen.findByPlaceholderText('Search operations…')
    ).toBeInTheDocument();
    expect(screen.queryByText('Single-Turn')).not.toBeInTheDocument();
    expect(screen.queryByText('Multi-Turn')).not.toBeInTheDocument();
  });
});
