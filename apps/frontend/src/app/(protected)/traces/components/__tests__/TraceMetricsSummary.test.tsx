import React from 'react';
import { act, render, screen, waitFor, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';
import TraceMetricsSummary from '../TraceMetricsSummary';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';

const getMetrics = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTelemetryClient: () => ({ getMetrics }),
  })),
}));

function metrics(
  overrides: Partial<TraceMetricsResponse> = {}
): TraceMetricsResponse {
  return {
    total_traces: 226,
    enriched_traces: 226,
    priced_traces: 226,
    total_spans: 3089,
    total_tokens: 571062,
    total_input_tokens: 412000,
    total_output_tokens: 159062,
    total_cost_usd: 0.19,
    total_input_cost_usd: 0.12,
    total_output_cost_usd: 0.07,
    models_used: ['gpt-4o', 'gemini-2.5-flash'],
    providers_used: ['openai', 'gemini'],
    error_spans: 40,
    error_rate: 0.0129,
    avg_duration_ms: 812,
    p50_duration_ms: 600,
    p95_duration_ms: 2400,
    p99_duration_ms: 4100,
    operation_breakdown: {
      'llm.invoke': 1800,
      'agent.invoke': 900,
      'function.invoke': 300,
      'tool.invoke': 60,
      'embedding.invoke': 29,
    },
    ...overrides,
  };
}

function renderTiles(props: Record<string, unknown> = {}) {
  return render(<TraceMetricsSummary projectId="project-1" {...props} />);
}

describe('TraceMetricsSummary', () => {
  beforeEach(() => {
    getMetrics.mockReset();
    getMetrics.mockResolvedValue(metrics());
  });

  it('renders nothing until the numbers arrive', () => {
    const { container } = renderTiles();

    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing without a project to scope to', () => {
    const { container } = renderTiles({ projectId: null });

    expect(container).toBeEmptyDOMElement();
    expect(getMetrics).not.toHaveBeenCalled();
  });

  it('counts traces, and names the kinds of work in them', async () => {
    renderTiles();

    expect(await screen.findByText('226')).toBeInTheDocument();
    expect(screen.getByText('5 span types')).toBeInTheDocument();
  });

  it('lists the span types on hover rather than in the tile', async () => {
    renderTiles();

    fireEvent.mouseOver(await screen.findByText('5 span types'));

    await waitFor(() =>
      expect(screen.getByRole('tooltip')).toHaveTextContent('llm.invoke')
    );
  });

  it('counts spans, with how many failed', async () => {
    renderTiles();

    expect(await screen.findByText('3,089')).toBeInTheDocument();
    expect(screen.getByText('40 errors · 99% ok')).toBeInTheDocument();
  });

  it('reports the failed spans the API counted, not a figure rebuilt from the rate', async () => {
    // error_rate is rounded to four places, so multiplying it back by the span
    // count lands on the wrong integer for most inputs: 3 errors in 11,667
    // spans rounds to 0.0003, which reads back as 4.
    getMetrics.mockResolvedValue(
      metrics({ total_spans: 11667, error_spans: 3, error_rate: 0.0003 })
    );
    renderTiles();

    expect(await screen.findByText(/3 errors/)).toBeInTheDocument();
    expect(screen.queryByText(/4 errors/)).not.toBeInTheDocument();
  });

  it('never claims everything is ok while reporting errors', async () => {
    // Rounding the share put "1 error \u00b7 100% ok" on screen for any scope
    // past 199 spans -- a sentence that argues with itself.
    getMetrics.mockResolvedValue(
      metrics({ total_spans: 11667, error_spans: 3, error_rate: 0.0003 })
    );
    renderTiles();

    expect(
      await screen.findByText('3 errors \u00b7 99% ok')
    ).toBeInTheDocument();
  });

  it('lists the span types busiest first, so the hover does not reshuffle', async () => {
    // The endpoint groups without an ORDER BY, so the keys arrive in whatever
    // order the database produced them.
    getMetrics.mockResolvedValue(
      metrics({
        operation_breakdown: {
          'tool.invoke': 60,
          'llm.invoke': 1800,
          'agent.invoke': 900,
        },
      })
    );
    renderTiles();

    fireEvent.mouseOver(await screen.findByText('3 span types'));

    await waitFor(() =>
      expect(screen.getByRole('tooltip')).toHaveTextContent(
        'llm.invoke, agent.invoke, tool.invoke'
      )
    );
  });

  it('says one error rather than one errors', async () => {
    getMetrics.mockResolvedValue(
      metrics({ error_spans: 1, error_rate: 0.0003 })
    );
    renderTiles();

    expect(await screen.findByText(/^1 error ·/)).toBeInTheDocument();
  });

  it('says so plainly when nothing errored', async () => {
    getMetrics.mockResolvedValue(metrics({ error_spans: 0, error_rate: 0 }));
    renderTiles();

    expect(await screen.findByText('No errors')).toBeInTheDocument();
  });

  it('leads usage with cost, and explains it with the token split', async () => {
    renderTiles();

    expect(await screen.findByText('$0.19')).toBeInTheDocument();
    // Asserted as one string rather than piece by piece: the separators
    // between the pieces are part of the sentence, and checking the pieces
    // alone once let a literal "\u00b7" reach the screen.
    expect(
      screen.getByText(
        '571,062 tokens \u00b7 412,000 input \u00b7 159,062 output'
      )
    ).toBeInTheDocument();
  });

  it('renders separators as characters, not as escape sequences', async () => {
    // JSX text children do not process backslash escapes, so a "\u00b7"
    // written into one reaches the browser verbatim. Waits for a tile first:
    // a negative assertion on an empty page passes for the wrong reason.
    renderTiles();
    await screen.findByText('$0.19');

    expect(document.body.textContent).not.toMatch(/\\u[0-9a-f]{4}/i);
  });

  it('names the models rather than only counting them', async () => {
    renderTiles();

    expect(await screen.findByText('2')).toBeInTheDocument();
    expect(screen.getByText('models')).toBeInTheDocument();
    expect(screen.getByText('openai/gpt-4o +1')).toBeInTheDocument();
  });

  it('falls back to tokens while enrichment is still pricing', async () => {
    getMetrics.mockResolvedValue(
      metrics({ enriched_traces: 100, priced_traces: 0, total_cost_usd: 0 })
    );
    renderTiles();

    expect(
      await screen.findByText('Working out what this cost')
    ).toBeInTheDocument();
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument();
  });

  it('says there is no cost data once enrichment has finished', async () => {
    getMetrics.mockResolvedValue(
      metrics({ priced_traces: 0, total_cost_usd: 0 })
    );
    renderTiles();

    expect(await screen.findByText('No cost data')).toBeInTheDocument();
    // The same explanation the test run summary offers, from the same module.
    expect(screen.getByRole('link', { name: 'Why?' })).toHaveAttribute(
      'href',
      expect.stringContaining('tracing/costs')
    );
  });

  it('shows a real $0.00 for a scope that was priced and free', async () => {
    getMetrics.mockResolvedValue(metrics({ total_cost_usd: 0 }));
    renderTiles();

    expect(await screen.findByText('$0.00')).toBeInTheDocument();
    expect(screen.queryByText('No cost data')).not.toBeInTheDocument();
  });

  it('holds every tile back for a project that has traced nothing', async () => {
    getMetrics.mockResolvedValue(
      metrics({ total_traces: 0, total_spans: 0, total_tokens: 0 })
    );
    const { container } = renderTiles();

    // Flush the fetch and the state update it triggers. Waiting only for the
    // call would pass whether or not the tiles are suppressed, since nothing
    // has re-rendered yet at that point.
    await act(async () => {
      await Promise.resolve();
    });

    expect(getMetrics).toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it('warns that the totals ignore filters the endpoint cannot honor', async () => {
    renderTiles({ hasUnsupportedFilters: true });

    expect(
      await screen.findByText(/Totals cover the whole project/)
    ).toBeInTheDocument();
  });

  it('narrows to one run when given one', async () => {
    renderTiles({ testRunId: 'run-1' });

    await waitFor(() => expect(getMetrics).toHaveBeenCalled());
    expect(getMetrics).toHaveBeenCalledWith(
      expect.objectContaining({ test_run_id: 'run-1' })
    );
  });
});
