import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import SpansTable from '../SpansTable';
import {
  TracesToolbarContext,
  type TracesToolbarState,
} from '../TracesToolbar';
import type { SpanSummary } from '@/utils/api-client/interfaces/telemetry';

const toolbarState: TracesToolbarState = {
  view: 'spans',
  onViewChange: jest.fn(),
  searchQuery: '',
  setSearchQuery: jest.fn(),
  openFilterDrawer: jest.fn(),
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
};

function span(overrides: Partial<SpanSummary> = {}): SpanSummary {
  return {
    id: 'db-1',
    span_id: 'span-1',
    trace_id: 'trace-1',
    parent_span_id: 'root-1',
    is_root: false,
    project_id: 'proj-1',
    span_name: 'ai.tool.invoke',
    span_type: 'tool.invoke',
    trace_name: 'function.visit_prep_chat',
    start_time: new Date().toISOString(),
    duration_ms: 1500,
    status_code: 'OK',
    environment: 'development',
    ...overrides,
  };
}

function renderTable(spans: SpanSummary[], onRowClick = jest.fn()) {
  render(
    <TracesToolbarContext.Provider value={toolbarState}>
      <SpansTable
        spans={spans}
        loading={false}
        onRowClick={onRowClick}
        totalCount={spans.length}
        page={0}
        pageSize={50}
        onPageChange={jest.fn()}
        onPageSizeChange={jest.fn()}
      />
    </TracesToolbarContext.Provider>
  );
  return { onRowClick };
}

describe('SpansTable', () => {
  it('shows the span type label, name and trace name', async () => {
    renderTable([span()]);

    expect(await screen.findByText('Tool')).toBeInTheDocument();
    expect(screen.getByText('ai.tool.invoke')).toBeInTheDocument();
    expect(screen.getByText('function.visit_prep_chat')).toBeInTheDocument();
  });

  it('shows model, tokens and status for an LLM call', async () => {
    renderTable([
      span({
        span_type: 'llm.invoke',
        span_name: 'ai.llm.invoke',
        model: 'gpt-4o',
        provider: 'openai',
        input_tokens: 1200,
        output_tokens: 300,
        total_tokens: 1500,
        cost_usd: 0.0123,
        status_code: 'ERROR',
      }),
    ]);

    expect(await screen.findByText('LLM call')).toBeInTheDocument();
    expect(screen.getByText('openai/gpt-4o')).toBeInTheDocument();
    expect(screen.getByText('1,500')).toBeInTheDocument();
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('shows a dash when the span has no model', async () => {
    renderTable([span()]);

    await screen.findByText('Tool');
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('keeps an unknown span type readable', async () => {
    renderTable([span({ span_type: 'chain' })]);

    expect(await screen.findByText('chain')).toBeInTheDocument();
  });

  it('passes the whole span on row click', async () => {
    const row = span();
    const { onRowClick } = renderTable([row]);

    fireEvent.click(await screen.findByText('ai.tool.invoke'));

    expect(onRowClick).toHaveBeenCalledWith(
      expect.objectContaining({
        trace_id: 'trace-1',
        project_id: 'proj-1',
        span_id: 'span-1',
      })
    );
  });

  it('uses the spans search placeholder', async () => {
    renderTable([]);

    expect(
      await screen.findByPlaceholderText('Search span name or ID…')
    ).toBeInTheDocument();
  });
});
