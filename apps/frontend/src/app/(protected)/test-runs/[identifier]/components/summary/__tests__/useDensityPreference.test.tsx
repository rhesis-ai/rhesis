import { renderHook, act } from '@testing-library/react';
import { useDensityPreference } from '../hooks/useDensityPreference';

const STORAGE_KEY = 'runSummary.metricTableDensity';

beforeEach(() => {
  localStorage.clear();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

describe('useDensityPreference', () => {
  it('defaults to detail while running, with no stored preference', () => {
    const { result } = renderHook(() =>
      useDensityPreference({ isTerminal: false, testRunId: 'run-1' })
    );
    expect(result.current.density).toBe('detail');
  });

  it('defaults to shape once terminal, with no stored preference', () => {
    const { result, rerender } = renderHook(
      ({ isTerminal }) =>
        useDensityPreference({ isTerminal, testRunId: 'run-1' }),
      { initialProps: { isTerminal: false } }
    );
    expect(result.current.density).toBe('detail');

    rerender({ isTerminal: true });
    expect(result.current.density).toBe('shape');
  });

  it('defaults straight to shape when mounted on an already-completed run', () => {
    const { result } = renderHook(() =>
      useDensityPreference({ isTerminal: true, testRunId: 'run-1' })
    );
    expect(result.current.density).toBe('shape');

    // No transition happened, so no auto-settle timer should be pending --
    // advancing time must not throw or change anything.
    act(() => {
      jest.advanceTimersByTime(2000);
    });
    expect(result.current.density).toBe('shape');
  });

  it('a persisted choice always wins over the run-state default', () => {
    localStorage.setItem(STORAGE_KEY, 'numbers');

    const { result } = renderHook(() =>
      useDensityPreference({ isTerminal: false, testRunId: 'run-1' })
    );
    expect(result.current.density).toBe('numbers');
  });

  it('persists an explicit choice immediately', () => {
    const { result } = renderHook(() =>
      useDensityPreference({ isTerminal: false, testRunId: 'run-1' })
    );
    expect(result.current.density).toBe('detail');

    act(() => {
      result.current.setDensity('numbers');
    });

    expect(result.current.density).toBe('numbers');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('numbers');
  });

  it('does not auto-settle for a run that was already terminal on mount', () => {
    const { result } = renderHook(() =>
      useDensityPreference({ isTerminal: true, testRunId: 'run-1' })
    );
    expect(result.current.density).toBe('shape');

    act(() => {
      jest.advanceTimersByTime(1500);
    });
    expect(result.current.density).toBe('shape');
  });

  it('an explicit choice makes a pending auto-settle a no-op', () => {
    const { result, rerender } = renderHook(
      ({ isTerminal }) =>
        useDensityPreference({ isTerminal, testRunId: 'run-1' }),
      { initialProps: { isTerminal: false } }
    );
    expect(result.current.density).toBe('detail');

    rerender({ isTerminal: true });

    act(() => {
      result.current.setDensity('numbers');
    });
    expect(result.current.density).toBe('numbers');

    act(() => {
      jest.advanceTimersByTime(1500);
    });
    // stored ('numbers') still wins over whatever autoSettled resolved to.
    expect(result.current.density).toBe('numbers');
  });

  it('never writes the auto-settled value to storage', () => {
    const { rerender } = renderHook(
      ({ isTerminal }) =>
        useDensityPreference({ isTerminal, testRunId: 'run-1' }),
      { initialProps: { isTerminal: false } }
    );

    rerender({ isTerminal: true });
    act(() => {
      jest.advanceTimersByTime(1500);
    });

    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  describe('forceDensity', () => {
    it('overrides an existing stored preference for this visit', () => {
      localStorage.setItem(STORAGE_KEY, 'numbers');

      const { result } = renderHook(() =>
        useDensityPreference({
          isTerminal: false,
          testRunId: 'run-1',
          forceDensity: 'detail',
        })
      );

      expect(result.current.density).toBe('detail');
    });

    it('does not persist the forced value to storage', () => {
      renderHook(() =>
        useDensityPreference({
          isTerminal: false,
          testRunId: 'run-1',
          forceDensity: 'detail',
        })
      );

      expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    });

    it('a later explicit choice overrides the forced value and persists', () => {
      const { result } = renderHook(() =>
        useDensityPreference({
          isTerminal: false,
          testRunId: 'run-1',
          forceDensity: 'detail',
        })
      );
      expect(result.current.density).toBe('detail');

      act(() => {
        result.current.setDensity('numbers');
      });

      expect(result.current.density).toBe('numbers');
      expect(localStorage.getItem(STORAGE_KEY)).toBe('numbers');
    });

    it('is a no-op when absent, leaving the stored preference in place', () => {
      localStorage.setItem(STORAGE_KEY, 'numbers');

      const { result } = renderHook(() =>
        useDensityPreference({
          isTerminal: false,
          testRunId: 'run-1',
          forceDensity: null,
        })
      );

      expect(result.current.density).toBe('numbers');
    });
  });

  describe('reused component instance across a run change', () => {
    // Next.js reuses this component across a client-side navigation between
    // two /test-runs/[identifier] pages (the "jump to the new run" redirect)
    // instead of remounting it -- these lock in that a forceDensity seed
    // still applies, and stale per-run state doesn't leak, when only
    // testRunId changes underneath an already-mounted hook instance.
    it('applies forceDensity for a new run even after an earlier run consumed its own', () => {
      const initialProps: { testRunId: string; forceDensity: 'detail' | null } =
        { testRunId: 'run-1', forceDensity: 'detail' };

      const { result, rerender } = renderHook(
        ({
          testRunId,
          forceDensity,
        }: {
          testRunId: string;
          forceDensity: 'detail' | null;
        }) =>
          useDensityPreference({ isTerminal: false, testRunId, forceDensity }),
        { initialProps }
      );
      expect(result.current.density).toBe('detail');

      // The user manually switches away, same as they could on any run.
      act(() => {
        result.current.setDensity('numbers');
      });
      expect(result.current.density).toBe('numbers');

      // A second redirect (e.g. a second rerun in the same session) lands
      // on a new run with its own forceDensity -- must not be swallowed by
      // the first run's already-consumed one-shot state.
      rerender({ testRunId: 'run-2', forceDensity: 'detail' });
      expect(result.current.density).toBe('detail');
    });

    it('falls back to the stored preference for a new run with no forceDensity', () => {
      localStorage.setItem(STORAGE_KEY, 'numbers');

      const initialProps: { testRunId: string; forceDensity: 'detail' | null } =
        { testRunId: 'run-1', forceDensity: 'detail' };

      const { result, rerender } = renderHook(
        ({
          testRunId,
          forceDensity,
        }: {
          testRunId: string;
          forceDensity: 'detail' | null;
        }) =>
          useDensityPreference({ isTerminal: false, testRunId, forceDensity }),
        { initialProps }
      );
      expect(result.current.density).toBe('detail');

      // Navigating to a run with no forced density (a normal click into a
      // run, not a redirect) must read the real stored preference, not
      // whatever the previous run happened to be forced to.
      rerender({ testRunId: 'run-2', forceDensity: null });
      expect(result.current.density).toBe('numbers');
    });

    it('does not carry a stale auto-settle into a freshly started run', () => {
      const { result, rerender } = renderHook(
        ({
          isTerminal,
          testRunId,
        }: {
          isTerminal: boolean;
          testRunId: string;
        }) => useDensityPreference({ isTerminal, testRunId }),
        { initialProps: { isTerminal: false, testRunId: 'run-1' } }
      );
      expect(result.current.density).toBe('detail');

      // run-1 finishes and auto-settles to shape.
      rerender({ isTerminal: true, testRunId: 'run-1' });
      act(() => {
        jest.advanceTimersByTime(1500);
      });
      expect(result.current.density).toBe('shape');

      // A brand new run-2 starts (still running) in the same mounted
      // instance -- must show detail, not the previous run's settled shape.
      rerender({ isTerminal: false, testRunId: 'run-2' });
      expect(result.current.density).toBe('detail');
    });
  });
});
