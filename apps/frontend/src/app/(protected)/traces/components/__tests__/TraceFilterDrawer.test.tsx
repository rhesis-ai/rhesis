import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import TraceFilterDrawer from '../TraceFilterDrawer';
import { EMPTY_TRACE_DRAWER_FILTERS } from '../trace-filter-params';

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'authenticated' }),
}));

jest.mock('@/hooks/useEndpoints', () => ({
  useEndpoints: () => ({ data: [] }),
}));

const mockReadActiveProjectId = jest.fn();
jest.mock('@/utils/active-project', () => ({
  readActiveProjectId: () => mockReadActiveProjectId(),
}));

const mockGetSpanFacets = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getProjectsClient: () => ({ getProjects: async () => [] }),
    getTelemetryClient: () => ({
      getProviders: async () => [],
      getSpanFacets: (...args: unknown[]) => mockGetSpanFacets(...args),
    }),
  })),
}));

beforeEach(() => {
  mockReadActiveProjectId.mockReset();
  mockReadActiveProjectId.mockReturnValue(undefined);
  mockGetSpanFacets.mockReset();
  mockGetSpanFacets.mockResolvedValue({
    span_types: [
      { value: 'tool.invoke', count: 12 },
      { value: 'span', count: 40 },
    ],
    span_names: [{ value: 'function.visit_prep_chat', count: 7 }],
    span_names_truncated: false,
    models: [],
  });
});

function renderDrawer(
  props: Partial<React.ComponentProps<typeof TraceFilterDrawer>> = {}
) {
  const onApply = jest.fn();
  render(
    <TraceFilterDrawer
      open
      onClose={jest.fn()}
      filters={EMPTY_TRACE_DRAWER_FILTERS}
      onApply={onApply}
      {...props}
    />
  );
  return { onApply };
}

describe('TraceFilterDrawer conversation filter', () => {
  it('applies the picked turn type', async () => {
    const { onApply } = renderDrawer();

    fireEvent.click(await screen.findByRole('button', { name: 'Multi-Turn' }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({ traceType: 'Multi-Turn' })
    );
  });

  it('clears the turn type when the active chip is clicked again', async () => {
    const { onApply } = renderDrawer({
      filters: { ...EMPTY_TRACE_DRAWER_FILTERS, traceType: 'Multi-Turn' },
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Multi-Turn' }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(onApply.mock.calls[0][0].traceType).toBeUndefined();
  });

  it('is hidden on a test run', async () => {
    renderDrawer({ fixedTestRunId: 'run-1' });

    expect(await screen.findByText('Evaluation')).toBeInTheDocument();
    expect(screen.queryByText('Conversation')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Single-Turn' })
    ).not.toBeInTheDocument();
  });
});

describe('TraceFilterDrawer spans view', () => {
  // "Evaluation" is also a span type label, so wait for the facet chips first:
  // the mocked facets hold no evaluation spans.
  it('drops the filters the spans list cannot apply', async () => {
    renderDrawer({ view: 'spans' });

    expect(
      await screen.findByRole('button', { name: /^Tool\s*12$/ })
    ).toBeInTheDocument();
    expect(screen.queryByText('Endpoint')).not.toBeInTheDocument();
    expect(screen.queryByText('Evaluation')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Pass' })
    ).not.toBeInTheDocument();
  });

  it('shows no span filters in the traces view', async () => {
    renderDrawer();

    expect(await screen.findByText('Evaluation')).toBeInTheDocument();
    expect(screen.queryByText('Span type')).not.toBeInTheDocument();
    expect(mockGetSpanFacets).not.toHaveBeenCalled();
  });

  it('lists span types from the facets with their counts', async () => {
    renderDrawer({ view: 'spans' });

    expect(
      await screen.findByRole('button', { name: /^Tool\s*12$/ })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /^Span\s*40$/ })
    ).toBeInTheDocument();
    // Types with no spans in scope are not offered.
    expect(
      screen.queryByRole('button', { name: /^LLM call/ })
    ).not.toBeInTheDocument();
  });

  it('falls back to every known type when facets fail', async () => {
    mockGetSpanFacets.mockRejectedValue(new Error('boom'));
    renderDrawer({ view: 'spans' });

    expect(
      await screen.findByRole('button', { name: 'LLM call' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tool' })).toBeInTheDocument();
  });

  it('applies picked type and root filters', async () => {
    const { onApply } = renderDrawer({ view: 'spans' });

    fireEvent.click(await screen.findByRole('button', { name: /^Tool\s*12$/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Child spans' }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({ spanTypes: ['tool.invoke'], isRoot: false })
    );
  });

  it('asks for facets under the draft filters', async () => {
    renderDrawer({
      view: 'spans',
      filters: { ...EMPTY_TRACE_DRAWER_FILTERS, spanTypes: ['tool.invoke'] },
    });

    await screen.findByRole('button', { name: /^Tool\s*12$/ });
    expect(mockGetSpanFacets).toHaveBeenLastCalledWith(
      expect.objectContaining({ span_type: ['tool.invoke'] })
    );
  });

  it('keeps span filters on a test run', async () => {
    renderDrawer({
      view: 'spans',
      fixedTestRunId: 'run-1',
      // TracesClient hands the drawer filters already scoped to the run.
      filters: { ...EMPTY_TRACE_DRAWER_FILTERS, testRunId: 'run-1' },
    });

    expect(
      await screen.findByRole('button', { name: /^Tool\s*12$/ })
    ).toBeInTheDocument();
    expect(screen.queryByText('Evaluation')).not.toBeInTheDocument();
    expect(mockGetSpanFacets).toHaveBeenLastCalledWith(
      expect.objectContaining({ test_run_id: 'run-1' })
    );
  });

  it('scopes facets to the active project, like the spans list', async () => {
    mockReadActiveProjectId.mockReturnValue('proj-active');
    renderDrawer({ view: 'spans' });

    await screen.findByRole('button', { name: /^Tool\s*12$/ });
    expect(mockGetSpanFacets).toHaveBeenLastCalledWith(
      expect.objectContaining({ project_id: 'proj-active' })
    );
  });

  it('keeps an explicit project over the active one', async () => {
    mockReadActiveProjectId.mockReturnValue('proj-active');
    renderDrawer({
      view: 'spans',
      filters: { ...EMPTY_TRACE_DRAWER_FILTERS, projectId: 'proj-picked' },
    });

    await screen.findByRole('button', { name: /^Tool\s*12$/ });
    expect(mockGetSpanFacets).toHaveBeenLastCalledWith(
      expect.objectContaining({ project_id: 'proj-picked' })
    );
  });

  it('drops old span names when a later facets request fails', async () => {
    mockGetSpanFacets
      .mockResolvedValueOnce({
        span_types: [{ value: 'tool.invoke', count: 12 }],
        span_names: [{ value: 'function.visit_prep_chat', count: 7 }],
        span_names_truncated: true,
        models: [],
      })
      .mockRejectedValueOnce(new Error('boom'));
    renderDrawer({ view: 'spans' });

    const tool = await screen.findByRole('button', { name: /^Tool\s*12$/ });
    expect(
      screen.getByText(/Showing the most common names/)
    ).toBeInTheDocument();
    fireEvent.click(tool);

    // The fallback shows every type; the names from the first fetch are gone.
    expect(
      await screen.findByRole('button', { name: 'LLM call' })
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Showing the most common names/)
    ).not.toBeInTheDocument();
  });
});
