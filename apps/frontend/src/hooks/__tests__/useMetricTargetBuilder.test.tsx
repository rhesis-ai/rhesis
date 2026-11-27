import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  TARGET_PREVIEW_DEBOUNCE_MS,
  TARGET_PREVIEW_TRACES,
  useMetricTargetPreview,
} from '../useMetricTargetBuilder';
import type { MetricTarget } from '@/utils/api-client/interfaces/metric';

jest.mock('@/hooks/useIsAuthenticated', () => ({
  useIsAuthenticated: () => true,
}));

const mockPreview = jest.fn();
jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getMetricsClient: () => ({ previewMetricTarget: mockPreview }),
  })),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  jest.useFakeTimers();
  mockPreview.mockReset();
  mockPreview.mockResolvedValue({
    traces: 1,
    matching_traces: 1,
    units: 1,
    not_applicable_traces: 0,
    samples: [],
  });
});

afterEach(() => jest.useRealTimers());

describe('useMetricTargetPreview', () => {
  it('previews the opened target at once, then edits once they stop', async () => {
    const { result, rerender } = renderHook(
      ({ target }: { target: MetricTarget | null }) =>
        useMetricTargetPreview('project-1', target),
      {
        wrapper,
        initialProps: { target: { on: 'turn' } as MetricTarget | null },
      }
    );
    expect(result.current.pending).toBe(false);
    await waitFor(() => expect(mockPreview).toHaveBeenCalledTimes(1));

    rerender({ target: { on: 'retrieval' } });
    rerender({ target: { on: 'tool_call' } });
    expect(result.current.pending).toBe(true);
    act(() => {
      jest.advanceTimersByTime(TARGET_PREVIEW_DEBOUNCE_MS - 1);
    });
    expect(mockPreview).toHaveBeenCalledTimes(1);

    act(() => {
      jest.advanceTimersByTime(1);
    });
    await waitFor(() => expect(mockPreview).toHaveBeenCalledTimes(2));
    expect(mockPreview.mock.calls[1][0]).toEqual({
      project_id: 'project-1',
      target: { on: 'tool_call' },
      traces: TARGET_PREVIEW_TRACES,
    });
    expect(result.current.pending).toBe(false);
  });

  it('previews nothing for an incomplete draft or without a project', () => {
    renderHook(() => useMetricTargetPreview('project-1', null), { wrapper });
    renderHook(() => useMetricTargetPreview(null, { on: 'turn' }), { wrapper });
    act(() => {
      jest.advanceTimersByTime(TARGET_PREVIEW_DEBOUNCE_MS * 2);
    });
    expect(mockPreview).not.toHaveBeenCalled();
  });
});
