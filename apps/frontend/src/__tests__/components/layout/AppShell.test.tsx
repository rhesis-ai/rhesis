import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { usePathname } from 'next/navigation';
import { AppShell, SidebarCollapseContext } from '@/components/layout/AppShell';

jest.mock('next/navigation', () => ({
  usePathname: jest.fn(() => '/projects'),
}));

describe('AppShell', () => {
  it('renders without crashing', () => {
    render(
      <AppShell sidebar={<div data-testid="sidebar">Sidebar</div>}>
        <div>Content</div>
      </AppShell>
    );
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
  });

  it('renders children in the main content area', () => {
    render(
      <AppShell sidebar={<div>Sidebar</div>}>
        <div data-testid="page-content">Page Content</div>
      </AppShell>
    );
    expect(screen.getByTestId('page-content')).toBeInTheDocument();
  });

  it('renders the optional topBar when provided', () => {
    render(
      <AppShell
        sidebar={<div>Sidebar</div>}
        topBar={<div data-testid="top-bar">Top Bar</div>}
      >
        <div>Content</div>
      </AppShell>
    );
    expect(screen.getByTestId('top-bar')).toBeInTheDocument();
  });

  it('does not render a header when topBar is not provided', () => {
    const { container } = render(
      <AppShell sidebar={<div>Sidebar</div>}>
        <div>Content</div>
      </AppShell>
    );
    expect(container.querySelector('header')).not.toBeInTheDocument();
  });

  it('provides SidebarCollapseContext with collapsed=false by default', () => {
    let capturedCollapsed: boolean | null = null;

    function Consumer() {
      const ctx = React.useContext(SidebarCollapseContext);
      capturedCollapsed = ctx.collapsed;
      return null;
    }

    render(
      <AppShell sidebar={<div>Sidebar</div>}>
        <Consumer />
      </AppShell>
    );

    expect(capturedCollapsed).toBe(false);
  });

  it('toggles collapsed state when toggle is called', async () => {
    const user = userEvent.setup();

    function Consumer() {
      const ctx = React.useContext(SidebarCollapseContext);
      return (
        <>
          <div data-testid="collapsed-state">
            {ctx.collapsed ? 'collapsed' : 'expanded'}
          </div>
          <button onClick={ctx.toggle} data-testid="toggle-btn">
            Toggle
          </button>
        </>
      );
    }

    render(
      <AppShell sidebar={<div>Sidebar</div>}>
        <Consumer />
      </AppShell>
    );

    expect(screen.getByTestId('collapsed-state')).toHaveTextContent('expanded');

    await user.click(screen.getByTestId('toggle-btn'));

    expect(screen.getByTestId('collapsed-state')).toHaveTextContent(
      'collapsed'
    );
  });

  it('removes content padding on full-bleed routes', () => {
    (usePathname as jest.Mock).mockReturnValue('/architect');

    const { container } = render(
      <AppShell sidebar={<div>Sidebar</div>}>
        <div data-testid="page-content">Page Content</div>
      </AppShell>
    );

    const contentWrapper = container.querySelector('main > div:last-child');
    expect(contentWrapper).toHaveStyle({ padding: '0px' });
  });

  it('keeps default content padding on standard routes', () => {
    (usePathname as jest.Mock).mockReturnValue('/projects');

    const { container } = render(
      <AppShell sidebar={<div>Sidebar</div>}>
        <div>Content</div>
      </AppShell>
    );

    const contentWrapper = container.querySelector('main > div:last-child');
    expect(contentWrapper).toHaveStyle({ padding: '32px' });
  });
});
