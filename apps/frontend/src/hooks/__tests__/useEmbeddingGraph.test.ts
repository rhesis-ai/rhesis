/* eslint-disable @typescript-eslint/no-explicit-any */
import { act, renderHook, waitFor } from '@testing-library/react';
import { useEmbeddingGraph } from '../useEmbeddingGraph';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Scatter2DGraph } from '@/utils/api-client/interfaces/embedding';

jest.mock('@/utils/api-client/client-factory');

const mockApiClientFactory = ApiClientFactory as jest.MockedClass<
  typeof ApiClientFactory
>;

const oldGraph: Scatter2DGraph = {
  computed_at: '2026-01-01T12:00:00Z',
  clusters: [{ cluster_index: 0, label: 'a', size: 1 }],
  points: [
    {
      embedding_id: 'e1',
      entity_id: 't1',
      entity_type: 'Test',
      cluster_index: 0,
      searchable_text: 'one',
      x: 0,
      y: 0,
    },
  ],
};

const newGraph: Scatter2DGraph = {
  ...oldGraph,
  computed_at: '2026-01-01T13:00:00Z',
};

describe('useEmbeddingGraph', () => {
  const mockTestSetsClient = {
    getEmbeddingGraph: jest.fn(),
    computeEmbeddingGraph: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockApiClientFactory.mockImplementation(
      () =>
        ({
          getTestSetsClient: () => mockTestSetsClient,
        }) as any
    );
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('keeps isComputing true on recompute until computed_at is newer', async () => {
    mockTestSetsClient.getEmbeddingGraph
      .mockResolvedValueOnce({ status: 'ready', graph: oldGraph })
      .mockResolvedValue({ status: 'ready', graph: oldGraph });
    mockTestSetsClient.computeEmbeddingGraph.mockResolvedValue({
      status: 'pending',
      task_id: 'task-1',
    });

    const { result } = renderHook(() =>
      useEmbeddingGraph('test-set-1', 'token')
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.graph).toEqual(oldGraph);

    await act(async () => {
      void result.current.computeGraph();
    });

    expect(result.current.isComputing).toBe(true);
    expect(mockTestSetsClient.computeEmbeddingGraph).toHaveBeenCalledTimes(1);

    await waitFor(() => {
      expect(
        mockTestSetsClient.getEmbeddingGraph.mock.calls.length
      ).toBeGreaterThan(1);
    });
    expect(result.current.isComputing).toBe(true);

    mockTestSetsClient.getEmbeddingGraph.mockResolvedValue({
      status: 'ready',
      graph: newGraph,
    });

    await act(async () => {
      await jest.runOnlyPendingTimersAsync();
    });

    await waitFor(() => {
      expect(result.current.isComputing).toBe(false);
    });
    expect(result.current.graph).toEqual(newGraph);
  });

  it('resets isComputing when enabled becomes false during poll', async () => {
    mockTestSetsClient.getEmbeddingGraph
      .mockResolvedValueOnce({ status: 'ready', graph: oldGraph })
      .mockResolvedValue({ status: 'ready', graph: oldGraph });
    mockTestSetsClient.computeEmbeddingGraph.mockResolvedValue({
      status: 'pending',
      task_id: 'task-1',
    });

    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useEmbeddingGraph('test-set-1', 'token', { enabled }),
      { initialProps: { enabled: true } }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      void result.current.computeGraph();
    });

    expect(result.current.isComputing).toBe(true);

    rerender({ enabled: false });

    await waitFor(() => {
      expect(result.current.isComputing).toBe(false);
    });
  });

  it('does not poll when graph has never been computed', async () => {
    mockTestSetsClient.getEmbeddingGraph.mockResolvedValue({
      status: 'pending',
    });

    const { result } = renderHook(() =>
      useEmbeddingGraph('test-set-1', 'token', { enabled: true })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isComputing).toBe(false);
    expect(result.current.graph).toBeNull();

    await act(async () => {
      await jest.advanceTimersByTimeAsync(30_000);
    });

    expect(mockTestSetsClient.getEmbeddingGraph).toHaveBeenCalledTimes(1);
  });

  it('resumes polling when enabled returns during recompute', async () => {
    mockTestSetsClient.getEmbeddingGraph
      .mockResolvedValueOnce({ status: 'ready', graph: oldGraph })
      .mockResolvedValue({ status: 'ready', graph: oldGraph });
    mockTestSetsClient.computeEmbeddingGraph.mockResolvedValue({
      status: 'pending',
      task_id: 'task-1',
    });

    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useEmbeddingGraph('test-set-1', 'token', { enabled }),
      { initialProps: { enabled: true } }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      void result.current.computeGraph();
    });

    expect(result.current.isComputing).toBe(true);

    rerender({ enabled: false });

    await waitFor(() => {
      expect(result.current.isComputing).toBe(false);
    });

    mockTestSetsClient.getEmbeddingGraph.mockResolvedValue({
      status: 'ready',
      graph: oldGraph,
    });

    rerender({ enabled: true });

    await waitFor(() => {
      expect(result.current.isComputing).toBe(true);
    });

    mockTestSetsClient.getEmbeddingGraph.mockResolvedValue({
      status: 'ready',
      graph: newGraph,
    });

    await act(async () => {
      await jest.runOnlyPendingTimersAsync();
    });

    await waitFor(() => {
      expect(result.current.isComputing).toBe(false);
      expect(result.current.graph).toEqual(newGraph);
    });
  });
});
