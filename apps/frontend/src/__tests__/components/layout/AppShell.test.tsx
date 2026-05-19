import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { AppShell, SidebarCollapseContext } from '@/components/layout/AppShell';

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
});
