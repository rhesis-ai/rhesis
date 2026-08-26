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
      useDensityPreference({ isTerminal: false })
    );
    expect(result.current.density).toBe('detail');
  });

  it('defaults to shape once terminal, with no stored preference', () => {
    const { result, rerender } = renderHook(
      ({ isTerminal }) => useDensityPreference({ isTerminal }),
      { initialProps: { isTerminal: false } }
    );
    expect(result.current.density).toBe('detail');

    rerender({ isTerminal: true });
    expect(result.current.density).toBe('shape');
  });

  it('defaults straight to shape when mounted on an already-completed run', () => {
    const { result } = renderHook(() =>
      useDensityPreference({ isTerminal: true })
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
      useDensityPreference({ isTerminal: false })
    );
    expect(result.current.density).toBe('numbers');
  });

  it('persists an explicit choice immediately', () => {
    const { result } = renderHook(() =>
      useDensityPreference({ isTerminal: false })
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
      useDensityPreference({ isTerminal: true })
    );
    expect(result.current.density).toBe('shape');

    act(() => {
      jest.advanceTimersByTime(1500);
    });
    expect(result.current.density).toBe('shape');
  });

  it('an explicit choice makes a pending auto-settle a no-op', () => {
    const { result, rerender } = renderHook(
      ({ isTerminal }) => useDensityPreference({ isTerminal }),
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
      ({ isTerminal }) => useDensityPreference({ isTerminal }),
      { initialProps: { isTerminal: false } }
    );

    rerender({ isTerminal: true });
    act(() => {
      jest.advanceTimersByTime(1500);
    });

    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
