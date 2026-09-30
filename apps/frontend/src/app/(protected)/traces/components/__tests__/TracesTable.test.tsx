import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import TracesTable from '../TracesTable';
import {
  TracesToolbarContext,
  type TracesToolbarState,
} from '../TracesToolbar';

function renderTable(toolbar: Partial<TracesToolbarState> = {}) {
  const state: TracesToolbarState = {
    view: 'traces',
    searchQuery: '',
    setSearchQuery: jest.fn(),
    openFilterDrawer: jest.fn(),
    hasActiveDrawerFilters: false,
    activeFilterCount: 0,
    ...toolbar,
  };
  render(
    <TracesToolbarContext.Provider value={state}>
      <TracesTable
        traces={[]}
        loading={false}
        onRowClick={jest.fn()}
        totalCount={0}
        page={0}
        pageSize={50}
        onPageChange={jest.fn()}
        onPageSizeChange={jest.fn()}
      />
    </TracesToolbarContext.Provider>
  );
}

describe('TracesTable toolbar', () => {
  it('has no turn-type pill tabs (the filter lives in the drawer)', async () => {
    renderTable();

    expect(
      await screen.findByPlaceholderText('Search operations…')
    ).toBeInTheDocument();
    expect(screen.queryByText('Single-Turn')).not.toBeInTheDocument();
    expect(screen.queryByText('Multi-Turn')).not.toBeInTheDocument();
  });

  it('switches to the spans view', async () => {
    const onViewChange = jest.fn();
    renderTable({ onViewChange });

    fireEvent.click(await screen.findByRole('button', { name: 'Spans' }));

    expect(onViewChange).toHaveBeenCalledWith('spans');
  });

  it('hides the switch when no handler is given', async () => {
    renderTable();

    await screen.findByPlaceholderText('Search operations…');
    expect(
      screen.queryByRole('button', { name: 'Spans' })
    ).not.toBeInTheDocument();
  });
});
