/**
 * The API access section: the example request in the list conventions, and
 * the roles that can read the log, from the RBAC roles API.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import AuditApiAccessSection, {
  exampleRequest,
} from '../AuditApiAccessSection';

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

describe('AuditApiAccessSection', () => {
  it('lists the roles that can read the log, highest first', async () => {
    render(<AuditApiAccessSection />);
    expect(await screen.findByText('Owner')).toBeInTheDocument();
    expect(screen.getByText('Auditor')).toBeInTheDocument();
    expect(screen.queryByText('Member')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open Roles' })).toHaveAttribute(
      'href',
      '/organizations/settings?tab=roles'
    );
    expect(screen.getByText('audit_log:read')).toBeInTheDocument();
  });

  it('does not call the roles API without RBAC', () => {
    rbacOn = false;
    render(<AuditApiAccessSection />);
    expect(
      screen.getByText('Owners and Admins can read the audit log.')
    ).toBeInTheDocument();
    expect(mockFetchRoles).not.toHaveBeenCalled();
  });
});
