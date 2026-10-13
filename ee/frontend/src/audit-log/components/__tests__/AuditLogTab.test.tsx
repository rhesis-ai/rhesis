/**
 * The tab's sections follow the viewer's capabilities, the `section` query
 * parameter picks one, and the header shows the retention from settings.
 */

import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import AuditLogTab from '../AuditLogTab';

let allowed = new Set<string>();
let loading = false;
let search = '';
const mockPush = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => new URLSearchParams(search),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: (capability: string) => !loading && allowed.has(capability),
  useCanWithStatus: (capability: string) => ({
    allowed: !loading && allowed.has(capability),
    loading,
  }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

const mockGetSettings = jest.fn();
jest.mock('../../api/audit-log-client', () => ({
  ...jest.requireActual('../../api/audit-log-client'),
  AuditLogClient: jest.fn().mockImplementation(() => ({
    getSettings: mockGetSettings,
  })),
}));

jest.mock('../AuditEventsGrid', () => ({
  __esModule: true,
  default: () => <div data-testid="events" />,
}));
jest.mock('../AuditExportsSection', () => ({
  __esModule: true,
  default: () => <div data-testid="exports" />,
}));
jest.mock('../AuditLogSettingsSection', () => ({
  __esModule: true,
  default: () => <div data-testid="settings" />,
}));
jest.mock('../StreamingSection', () => ({
  __esModule: true,
  default: () => <div data-testid="streaming" />,
}));
jest.mock('../AuditApiAccessSection', () => ({
  __esModule: true,
  default: () => <div data-testid="api" />,
}));

beforeEach(() => {
  jest.clearAllMocks();
  allowed = new Set(['audit_log:read', 'audit_log:export']);
  loading = false;
  search = '';
  mockGetSettings.mockResolvedValue({
    retention_days: 1095,
    max_retention_days: 1095,
    below_eu_ai_act_minimum: false,
    mask_ip: true,
    include_content: false,
    scheduled_jobs_running: true,
  });
});

describe('AuditLogTab', () => {
  it('opens on Events and shows the retention badge', async () => {
    render(<AuditLogTab />);
    expect(screen.getByTestId('events')).toBeInTheDocument();
    expect(await screen.findByText('Retention: 3 years')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Exports' })).toBeInTheDocument();
  });

  it('opens the section named in the URL, and writes the choice back', () => {
    search = 'tab=audit-log&section=exports';
    render(<AuditLogTab />);
    expect(screen.getByTestId('exports')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Settings' }));
    expect(mockPush).toHaveBeenCalledWith('?tab=audit-log&section=settings', {
      scroll: false,
    });
  });

  it('hides Exports from a reader who cannot export', () => {
    allowed = new Set(['audit_log:read']);
    search = 'section=exports';
    render(<AuditLogTab />);
    expect(
      screen.queryByRole('tab', { name: 'Exports' })
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId('exports')).not.toBeInTheDocument();
    expect(screen.getByTestId('events')).toBeInTheDocument();
  });

  it('hides Streaming from those who cannot manage the audit log', () => {
    render(<AuditLogTab />);
    expect(
      screen.queryByRole('tab', { name: 'Streaming' })
    ).not.toBeInTheDocument();
  });

  it('opens Streaming for those who can manage the audit log', () => {
    allowed = new Set(['audit_log:read', 'audit_log:manage']);
    search = 'section=streaming';
    render(<AuditLogTab />);
    expect(screen.getByTestId('streaming')).toBeInTheDocument();
  });

  it('denies access without any audit log capability', () => {
    allowed = new Set();
    render(<AuditLogTab />);
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
    expect(screen.getByText(/the audit log/i)).toBeInTheDocument();
    expect(mockGetSettings).not.toHaveBeenCalled();
  });

  it('waits for permissions before choosing a section', () => {
    loading = true;
    render(<AuditLogTab />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByTestId('events')).not.toBeInTheDocument();
  });
});
