import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import { PageLayout } from '@/components/layout/PageLayout';

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
