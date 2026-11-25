import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import TracesTable from '../TracesTable';
import type { TraceSummary } from '@/utils/api-client/interfaces/telemetry';
import {
  TracesToolbarContext,
  type TracesToolbarState,
} from '../TracesToolbar';

function renderTable(
  toolbar: Partial<TracesToolbarState> = {},
  traces: TraceSummary[] = []
) {
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
        traces={traces}
        loading={false}
        onRowClick={jest.fn()}
        totalCount={traces.length}
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

describe('TracesTable evaluation column', () => {
  const skipped: TraceSummary = {
    trace_id: 'trace-1',
    project_id: 'project-1',
    environment: 'development',
    start_time: '2026-11-23T10:00:00Z',
    duration_ms: 120,
    span_count: 1,
    root_operation: 'chat',
    trace_metrics_status: 'Skipped',
    execution: 'not_run',
    verdict: null,
    has_annotations: true,
    last_annotation: {
      status: { name: 'Pass' },
    } as TraceSummary['last_annotation'],
  };

  it('shows a skipped trace without an annotation conflict', async () => {
    renderTable({}, [skipped]);

    expect(await screen.findByText('Skipped')).toBeInTheDocument();
    expect(screen.getByLabelText('Annotated')).toBeInTheDocument();
  });
});

describe('TracesTable agent column', () => {
  const base: TraceSummary = {
    trace_id: 'trace-1',
    project_id: 'project-1',
    environment: 'development',
    start_time: '2026-11-23T10:00:00Z',
    duration_ms: 120,
    span_count: 1,
    root_operation: 'ai.agent.run',
    execution: 'not_run',
    verdict: null,
  };

  it('shows the agent that ran the trace', async () => {
    renderTable({}, [{ ...base, agent_name: 'planner' }]);

    expect(await screen.findByText('Agent')).toBeInTheDocument();
    expect(screen.getByText('planner')).toBeInTheDocument();
  });
});
