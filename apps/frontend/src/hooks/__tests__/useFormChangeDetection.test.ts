import { renderHook, act } from '@testing-library/react';
import { useFormChangeDetection } from '../useFormChangeDetection';

describe('useFormChangeDetection', () => {
  it('returns no changes when data is identical', () => {
    const data = { name: 'Alice', email: 'alice@example.com' };
    const { result } = renderHook(() =>
      useFormChangeDetection({ initialData: data, currentData: data })
    );

    expect(result.current.hasChanges).toBe(false);
  });

  it('detects changes in string fields', () => {
    const initial = { name: 'Alice', email: 'alice@example.com' };
    const current = { name: 'Bob', email: 'alice@example.com' };
    const { result } = renderHook(() =>
      useFormChangeDetection({ initialData: initial, currentData: current })
    );

    expect(result.current.hasChanges).toBe(true);
  });

  it('ignores whitespace-only differences in strings', () => {
    const initial = { name: 'Alice', email: 'alice@example.com' };
    const current = { name: '  Alice  ', email: 'alice@example.com' };
    const { result } = renderHook(() =>
      useFormChangeDetection({ initialData: initial, currentData: current })
    );

    expect(result.current.hasChanges).toBe(false);
  });

  it('treats null and empty string as equal', () => {
    const initial: Record<string, string | null> = { name: null, value: '' };
    const current: Record<string, string | null> = { name: '', value: null };
    const { result } = renderHook(() =>
      useFormChangeDetection({ initialData: initial, currentData: current })
    );

    expect(result.current.hasChanges).toBe(false);
  });

  it('treats undefined and empty string as equal', () => {
    const initial: Record<string, string | undefined> = {
      name: undefined,
      value: '',
    };
    const current: Record<string, string | undefined> = {
      name: '',
      value: undefined,
    };
    const { result } = renderHook(() =>
      useFormChangeDetection({ initialData: initial, currentData: current })
    );

    expect(result.current.hasChanges).toBe(false);
  });

  it('detects changes in boolean fields', () => {
    const initial = { active: true, name: 'test' };
    const current = { active: false, name: 'test' };
    const { result } = renderHook(() =>
      useFormChangeDetection({ initialData: initial, currentData: current })
    );

    expect(result.current.hasChanges).toBe(true);
  });

  it('detects changes in number fields', () => {
    const initial = { count: 1, name: 'test' };
    const current = { count: 2, name: 'test' };
    const { result } = renderHook(() =>
      useFormChangeDetection({ initialData: initial, currentData: current })
    );

    expect(result.current.hasChanges).toBe(true);
  });

  it('resetChanges clears the change detection', () => {
    const initial = { name: 'Alice' };
    const current = { name: 'Bob' };
    const { result } = renderHook(() =>
      useFormChangeDetection({ initialData: initial, currentData: current })
    );

    expect(result.current.hasChanges).toBe(true);

    act(() => {
      result.current.resetChanges();
    });

    // After reset, currentData becomes the new baseline
    expect(result.current.hasChanges).toBe(false);
  });

  it('updates when initialData reference changes', () => {
    const initial1 = { name: 'Alice' };
    const initial2 = { name: 'Bob' };
    const current = { name: 'Bob' };

    const { result, rerender } = renderHook(
      ({ initialData, currentData }) =>
        useFormChangeDetection({ initialData, currentData }),
      { initialProps: { initialData: initial1, currentData: current } }
    );

    // Bob !== Alice => changes
    expect(result.current.hasChanges).toBe(true);

    // Update initialData to match current
    rerender({ initialData: initial2, currentData: current });
    expect(result.current.hasChanges).toBe(false);
  });
});
