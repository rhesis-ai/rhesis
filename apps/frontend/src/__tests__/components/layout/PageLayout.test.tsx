import React from 'react';
import { act, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import { PageLayout } from '@/components/layout/PageLayout';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import { SKELETON_DELAY_MS } from '@/components/loading/DelayedReveal';
import { LiveAnnouncerProvider } from '@/components/common/LiveAnnouncer';

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider theme={lightTheme}>{ui}</ThemeProvider>);
}

describe('PageLayout', () => {
  it('renders without crashing', () => {
    const { container } = renderWithTheme(
      <PageLayout>
        <div>Content</div>
      </PageLayout>
    );
    expect(container).toBeInTheDocument();
  });

  it('renders the title when provided', () => {
    renderWithTheme(
      <PageLayout title="Test Page">
        <div>Content</div>
      </PageLayout>
    );
    expect(
      screen.getByRole('heading', { name: 'Test Page' })
    ).toBeInTheDocument();
  });

  it('renders the description when provided', () => {
    renderWithTheme(
      <PageLayout title="Test Page" description="A description of the page">
        <div>Content</div>
      </PageLayout>
    );
    expect(screen.getByText('A description of the page')).toBeInTheDocument();
  });

  it('renders children', () => {
    renderWithTheme(
      <PageLayout>
        <div data-testid="child-content">Child Content</div>
      </PageLayout>
    );
    expect(screen.getByTestId('child-content')).toBeInTheDocument();
  });

  it('renders the actions slot when provided', () => {
    renderWithTheme(
      <PageLayout
        title="Test Page"
        actions={<button data-testid="action-btn">Create</button>}
      >
        <div>Content</div>
      </PageLayout>
    );
    expect(screen.getByTestId('action-btn')).toBeInTheDocument();
  });

  it('renders breadcrumbs when provided', () => {
    renderWithTheme(
      <PageLayout
        breadcrumbs={[{ label: 'Home', href: '/' }, { label: 'Tests' }]}
      >
        <div>Content</div>
      </PageLayout>
    );
    expect(
      screen.getByRole('navigation', { name: 'breadcrumb' })
    ).toBeInTheDocument();
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Tests')).toBeInTheDocument();
  });

  it('renders breadcrumb links with correct href', () => {
    renderWithTheme(
      <PageLayout
        breadcrumbs={[{ label: 'Home', href: '/' }, { label: 'Tests' }]}
      >
        <div>Content</div>
      </PageLayout>
    );
    const homeLink = screen.getByRole('link', { name: 'Home' });
    expect(homeLink).toHaveAttribute('href', '/');
  });

  it('does not render a header when no title, description, breadcrumbs or actions are given', () => {
    renderWithTheme(
      <PageLayout>
        <div data-testid="only-child">Only Child</div>
      </PageLayout>
    );
    expect(screen.getByTestId('only-child')).toBeInTheDocument();
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
  });
});

describe('PageLayout as a loading view', () => {
  function renderLoading(ui: React.ReactElement) {
    return renderWithTheme(
      <LiveAnnouncerProvider>
        <SkeletonMode>{ui}</SkeletonMode>
      </LiveAnnouncerProvider>
    );
  }

  afterEach(() => {
    jest.useRealTimers();
  });

  it('marks the page busy', () => {
    const { container } = renderLoading(
      <PageLayout title="Tests">
        <div />
      </PageLayout>
    );
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
  });

  it('is not busy outside a loading view', () => {
    const { container } = renderWithTheme(
      <PageLayout title="Tests">
        <div />
      </PageLayout>
    );
    expect(container.querySelector('[aria-busy]')).toBeNull();
  });

  it('announces the page it is loading, after the placeholder delay', () => {
    jest.useFakeTimers();
    renderLoading(
      <PageLayout title="Tests">
        <div />
      </PageLayout>
    );
    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('');

    // The delay, then the live region's own clear-and-set step.
    act(() => {
      jest.advanceTimersByTime(SKELETON_DELAY_MS + 200);
    });
    expect(status).toHaveTextContent('Loading Tests');
  });

  it('stays quiet when the page arrives before the delay', () => {
    jest.useFakeTimers();
    const view = (loading: boolean) => (
      <ThemeProvider theme={lightTheme}>
        <LiveAnnouncerProvider>
          {loading && (
            <SkeletonMode>
              <PageLayout title="Tests">
                <div />
              </PageLayout>
            </SkeletonMode>
          )}
        </LiveAnnouncerProvider>
      </ThemeProvider>
    );
    const { rerender } = render(view(true));
    rerender(view(false));
    act(() => {
      jest.advanceTimersByTime(SKELETON_DELAY_MS + 200);
    });
    expect(screen.getByRole('status')).toHaveTextContent('');
  });

  it('keeps metadata labels without values away from screen readers', () => {
    renderLoading(
      <PageLayout title="Tests" metadata={<span>created by:</span>}>
        <div />
      </PageLayout>
    );
    expect(screen.getByText('created by:').closest('[inert]')).not.toBeNull();
  });
});
