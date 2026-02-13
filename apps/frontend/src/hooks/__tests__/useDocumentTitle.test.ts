import { renderHook } from '@testing-library/react';
import { useDocumentTitle } from '../useDocumentTitle';

describe('useDocumentTitle', () => {
  const originalTitle = document.title;

  afterEach(() => {
    document.title = originalTitle;
  });

  it('sets document title with template', () => {
    renderHook(() => useDocumentTitle('Dashboard'));
    expect(document.title).toBe('Dashboard | Rhesis AI');
  });

  it('does not change title when null is passed', () => {
    document.title = 'Original Title';
    renderHook(() => useDocumentTitle(null));
    expect(document.title).toBe('Original Title');
  });

  it('restores default title on unmount', () => {
    const { unmount } = renderHook(() => useDocumentTitle('Settings'));
    expect(document.title).toBe('Settings | Rhesis AI');

    unmount();
    expect(document.title).toBe('Rhesis AI');
  });

  it('updates title when value changes', () => {
    const { rerender } = renderHook(({ title }) => useDocumentTitle(title), {
      initialProps: { title: 'Page A' as string | null },
    });

    expect(document.title).toBe('Page A | Rhesis AI');

    rerender({ title: 'Page B' });
    expect(document.title).toBe('Page B | Rhesis AI');
  });

  it('handles empty string (truthy check)', () => {
    document.title = 'Original Title';
    renderHook(() => useDocumentTitle(''));
    // Empty string is falsy, so title should not be changed
    expect(document.title).toBe('Original Title');
  });
});
