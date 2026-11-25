import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import SkeletonPageHeader from '../SkeletonPageHeader';
import { Capability } from '@/constants/capabilities';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { useAmbientPermissions } from '@/contexts/PermissionsContext';

jest.mock('@/contexts/PermissionsContext', () => ({
  useAmbientPermissions: jest.fn(),
}));
const mockAmbient = useAmbientPermissions as unknown as jest.Mock;

const ambient = (overrides: object) => ({
  permitted_actions: [],
  loading: false,
  error: null,
  enabled: true,
  ...overrides,
});

const renderHeader = (props: React.ComponentProps<typeof SkeletonPageHeader>) =>
  render(
    <ThemeProvider theme={lightTheme}>
      <SkeletonPageHeader {...props} />
    </ThemeProvider>
  );

const fabPlaceholders = (container: HTMLElement) =>
  container.querySelectorAll('.MuiSkeleton-circular').length;

describe('SkeletonPageHeader', () => {
  beforeEach(() => mockAmbient.mockReturnValue(ambient({ enabled: false })));

  it('draws a known title and description as the page does', () => {
    renderHeader({
      title: PAGE_HEADERS.tests.title,
      description: PAGE_HEADERS.tests.description,
    });

    expect(
      screen.getByRole('heading', { level: 1, name: 'Tests' })
    ).toBeInTheDocument();
    expect(
      screen.getByText(PAGE_HEADERS.tests.description)
    ).toBeInTheDocument();
  });

  it('draws one placeholder per button the role gets', () => {
    mockAmbient.mockReturnValue(
      ambient({ permitted_actions: [Capability.Test.CREATE] })
    );

    const { container } = renderHeader({
      actions: PAGE_HEADERS.tests.actions,
    });

    // Tests offers import and create; this role may only create.
    expect(fabPlaceholders(container)).toBe(1);
  });

  it('counts a button gated by any of several capabilities once', () => {
    mockAmbient.mockReturnValue(
      ambient({ permitted_actions: [Capability.Owasp.CREATE] })
    );

    const { container } = renderHeader({
      actions: PAGE_HEADERS.testSets.actions,
    });

    expect(fabPlaceholders(container)).toBe(1);
  });

  it('draws every button when RBAC is off and none while permissions load', () => {
    const { container, rerender } = renderHeader({
      actions: PAGE_HEADERS.testSets.actions,
    });
    expect(fabPlaceholders(container)).toBe(4);

    mockAmbient.mockReturnValue(ambient({ loading: true }));
    rerender(
      <ThemeProvider theme={lightTheme}>
        <SkeletonPageHeader actions={PAGE_HEADERS.testSets.actions} />
      </ThemeProvider>
    );
    expect(fabPlaceholders(container)).toBe(0);
  });

  it('links a known first crumb and holds the unknown ones as placeholders', () => {
    const { container } = renderHeader({
      breadcrumbCount: 2,
      crumbs: [directoryCrumb(PAGE_HEADERS.testRuns)],
      actionCount: 0,
    });

    expect(screen.getByRole('link', { name: 'Test Runs' })).toHaveAttribute(
      'href',
      '/test-runs'
    );
    // The entity's own crumb, plus title and description lines, wait.
    expect(container.querySelectorAll('.MuiSkeleton-text')).toHaveLength(3);
  });
});
