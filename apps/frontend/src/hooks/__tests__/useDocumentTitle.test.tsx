import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { useDocumentTitle } from '../useDocumentTitle';
import { NavigationItemsContext } from '@/contexts/NavigationItemsContext';
import type { BrandingProps } from '@/types/navigation';
import { detailPageTitle } from '@/utils/document-title';

/** Renders the hook under a branding context, or none at all. */
function wrapperFor(productName?: string) {
  const branding = productName
    ? ({ title: 'Acme', productName } as BrandingProps)
    : null;

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <NavigationItemsContext.Provider value={{ navigation: [], branding }}>
        {children}
      </NavigationItemsContext.Provider>
    );
  };
}

describe('useDocumentTitle', () => {
  const originalTitle = document.title;

  afterEach(() => {
    document.title = originalTitle;
  });

  it('suffixes the title with the resolved product name', () => {
    renderHook(() => useDocumentTitle('Dashboard'), {
      wrapper: wrapperFor('Acme Testing'),
    });

    expect(document.title).toBe('Dashboard | Acme Testing');
  });

  it('falls back to the Rhesis name when branding has not resolved', () => {
    renderHook(() => useDocumentTitle('Dashboard'), { wrapper: wrapperFor() });

    expect(document.title).toBe('Dashboard | Rhesis AI');
  });

  it('does not change the title when null is passed', () => {
    document.title = 'Original Title';
    renderHook(() => useDocumentTitle(null), { wrapper: wrapperFor('Acme') });

    expect(document.title).toBe('Original Title');
  });

  it('restores the product name on unmount', () => {
    const { unmount } = renderHook(() => useDocumentTitle('Settings'), {
      wrapper: wrapperFor('Acme Testing'),
    });
    expect(document.title).toBe('Settings | Acme Testing');

    unmount();
    expect(document.title).toBe('Acme Testing');
  });

  it('updates when the title changes', () => {
    const { rerender } = renderHook(
      ({ title }: { title: string }) => useDocumentTitle(title),
      { wrapper: wrapperFor('Acme'), initialProps: { title: 'First' } }
    );
    expect(document.title).toBe('First | Acme');

    rerender({ title: 'Second' });
    expect(document.title).toBe('Second | Acme');
  });

  it('ignores an empty title', () => {
    document.title = 'Original Title';
    renderHook(() => useDocumentTitle(''), { wrapper: wrapperFor('Acme') });

    expect(document.title).toBe('Original Title');
  });

  it('restores the title it replaced on unmount', () => {
    document.title = 'Traces | Acme';
    const { unmount } = renderHook(() => useDocumentTitle('Run · Traces'), {
      wrapper: wrapperFor('Acme'),
    });
    expect(document.title).toBe('Run · Traces | Acme');

    unmount();
    expect(document.title).toBe('Traces | Acme');
  });

  it('leaves a title set by the next page alone on unmount', () => {
    const { unmount } = renderHook(() => useDocumentTitle('Settings'), {
      wrapper: wrapperFor('Acme'),
    });
    document.title = 'Metrics | Acme';

    unmount();
    expect(document.title).toBe('Metrics | Acme');
  });

  it('re-applies the title when route metadata inserts a later <title>', async () => {
    renderHook(() => useDocumentTitle('Policy · Metrics'), {
      wrapper: wrapperFor('Acme'),
    });

    const streamed = document.createElement('title');
    streamed.textContent = 'Metrics | Acme';
    document.head.prepend(streamed);

    await waitFor(() => expect(document.title).toBe('Policy · Metrics | Acme'));
    streamed.remove();
  });
});

describe('detailPageTitle', () => {
  it('joins the item name and section', () => {
    expect(detailPageTitle('Policy Accuracy', 'Metrics')).toBe(
      'Policy Accuracy · Metrics'
    );
  });

  it('falls back to the section while the name is missing', () => {
    expect(detailPageTitle(undefined, 'Metrics')).toBe('Metrics');
    expect(detailPageTitle('  ', 'Metrics')).toBe('Metrics');
  });
});
