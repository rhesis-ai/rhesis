/**
 * The API access card's example request in the list conventions, and the
 * read access card's roles, from the RBAC roles API.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import AuditApiAccessCard, {
  AuditReadAccessCard,
  exampleRequest,
} from '../AuditApiAccessCard';

let rbacOn = true;
jest.mock('@/contexts/FeaturesContext', () => ({
  useFeature: () => rbacOn,
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn(), close: jest.fn() }),
}));

const mockFetchRoles = jest.fn();
jest.mock('../../../rbac/api/role-cache', () => ({
  fetchRoles: () => mockFetchRoles(),
}));

function role(name: string, level: number, permissions: string[]) {
  return {
    id: name,
    name,
    display_name: name,
    description: '',
    scope: 'org',
    level,
    is_built_in: true,
    organization_id: null,
    member_count: 0,
    permissions: permissions.map(p => ({
      id: p,
      name: p,
      display_name: p,
      resource_type: p.split(':')[0],
      action: p.split(':')[1],
      scope: 'org',
      is_retired: false,
    })),
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  rbacOn = true;
  mockFetchRoles.mockResolvedValue([
    role('Member', 60, ['endpoint:read']),
    role('Auditor', 70, ['audit_log:read', 'audit_log:export']),
    role('Owner', 100, ['audit_log:read', 'audit_log:manage']),
  ]);
});

describe('exampleRequest', () => {
  it('uses OData $filter and the 100-row limit, with no /api/v1', () => {
    const text = exampleRequest(
      'https://api.example.com',
      new Date('2026-09-13T12:00:00Z')
    );
    expect(text).toContain('"https://api.example.com/audit-events"');
    expect(text).toContain(
      "$filter=startswith(action,'endpoint.') and occurred_at ge 2026-09-13"
    );
    expect(text).toContain('limit=100');
  });
});

describe('AuditApiAccessCard', () => {
  it('shows the example and the scope it needs', () => {
    render(<AuditApiAccessCard />);
    expect(screen.getByText(/curl -G/)).toBeInTheDocument();
    expect(screen.getByText('audit_log:read')).toBeInTheDocument();
  });
});

describe('AuditReadAccessCard', () => {
  it('lists every role, highest first, ticking those that read the log', async () => {
    render(<AuditReadAccessCard />);
    const owner = await screen.findByRole('checkbox', {
      name: 'Owner can read the audit log',
    });
    expect(owner).toBeChecked();
    expect(
      screen.getByRole('checkbox', { name: 'Auditor can read the audit log' })
    ).toBeChecked();
    expect(
      screen.getByRole('checkbox', { name: 'Member cannot read the audit log' })
    ).not.toBeChecked();
    const names = screen
      .getAllByRole('checkbox')
      .map(box => box.getAttribute('aria-label'));
    expect(names[0]).toMatch(/^Owner/);
    expect(names[2]).toMatch(/^Member/);
    expect(screen.getByRole('link', { name: 'Edit roles' })).toHaveAttribute(
      'href',
      '/organizations/settings?tab=roles'
    );
  });

  it('does not call the roles API without RBAC', () => {
    rbacOn = false;
    render(<AuditReadAccessCard />);
    expect(
      screen.getByText('Owners and Admins can read the audit log.')
    ).toBeInTheDocument();
    expect(mockFetchRoles).not.toHaveBeenCalled();
  });
});
