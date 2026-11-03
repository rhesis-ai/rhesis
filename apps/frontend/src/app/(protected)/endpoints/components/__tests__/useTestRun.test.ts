import { act, renderHook } from '@testing-library/react';
import { useTestRun, SLOW_API_MS } from '../useTestRun';
import type { EndpointTestResult } from '../TestResponseCard';

/** A test call the test resolves by hand. */
function deferred() {
  let resolve: (r: EndpointTestResult) => void = () => undefined;
  const promise = new Promise<EndpointTestResult>(r => {
    resolve = r;
  });
  return { promise, resolve };
}

describe('useTestRun', () => {
  afterEach(() => jest.useRealTimers());

  it('shows only the newest run when an older one answers last', async () => {
    const { result } = renderHook(() => useTestRun());
    const first = deferred();
    const second = deferred();

    act(() => {
      void result.current.run(() => first.promise);
    });
    act(() => {
      void result.current.run(() => second.promise);
    });

    await act(async () => {
      second.resolve({ success: true, response: { which: 'second' } });
    });
    await act(async () => {
      first.resolve({ success: false, error: 'old' });
    });

    expect(result.current.result).toEqual({
      success: true,
      response: { which: 'second' },
    });
    expect(result.current.isTesting).toBe(false);
  });

  it('keeps waiting while a newer run is still open', async () => {
    const { result } = renderHook(() => useTestRun());
    const first = deferred();
    const second = deferred();
    act(() => {
      void result.current.run(() => first.promise);
    });
    act(() => {
      void result.current.run(() => second.promise);
    });

    await act(async () => {
      first.resolve({ success: true });
    });

    expect(result.current.isTesting).toBe(true);
    expect(result.current.result).toBeNull();
  });

  it('cancels: stops waiting and ignores the late answer', async () => {
    const { result } = renderHook(() => useTestRun());
    const call = deferred();
    const onPassed = jest.fn();
    act(() => {
      void result.current.run(() => call.promise, onPassed);
    });

    act(() => result.current.cancel());
    expect(result.current.isTesting).toBe(false);

    await act(async () => {
      call.resolve({ success: true });
    });
    expect(result.current.result).toBeNull();
    expect(onPassed).not.toHaveBeenCalled();
  });

  it('marks the API slow once a run takes longer than the threshold', async () => {
    jest.useFakeTimers();
    jest.setSystemTime(0);
    const { result } = renderHook(() => useTestRun());
    const call = deferred();
    act(() => {
      void result.current.run(() => call.promise);
    });

    jest.setSystemTime(SLOW_API_MS + 1);
    await act(async () => {
      call.resolve({ success: true });
    });

    expect(result.current.isSlow).toBe(true);
  });

  it('turns a call that throws into a failed result and stops waiting', async () => {
    const { result } = renderHook(() => useTestRun());
    const onPassed = jest.fn();

    await act(async () => {
      await result.current.run(async () => {
        throw new Error('network down');
      }, onPassed);
    });

    expect(result.current.isTesting).toBe(false);
    expect(result.current.result).toEqual({
      success: false,
      error: 'network down',
    });
    expect(onPassed).not.toHaveBeenCalled();
  });

  it('does not mark a quick API as slow', async () => {
    const { result } = renderHook(() => useTestRun());
    await act(async () => {
      await result.current.run(async () => ({ success: true }));
    });
    expect(result.current.isSlow).toBe(false);
  });
});
