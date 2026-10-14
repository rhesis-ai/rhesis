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
jest.mock('../AuditSettingsCards', () => ({
  AuditRetentionCard: () => <div data-testid="retention" />,
  AuditPrivacyCard: () => <div data-testid="privacy" />,
  AuditSettingsNotices: () => null,
}));
jest.mock('../StreamingSection', () => ({
  __esModule: true,
  default: () => <div data-testid="streaming" />,
}));
jest.mock('../AuditApiAccessCard', () => ({
  __esModule: true,
  default: () => <div data-testid="api" />,
  AuditReadAccessCard: () => <div data-testid="readers" />,
}));

const SETTINGS_TAB = 'Retention, export & access';

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
    expect(screen.getAllByRole('tab').map(tab => tab.textContent)).toEqual([
      'Events',
      SETTINGS_TAB,
    ]);
  });

  it('opens the section named in the URL, and writes the choice back', () => {
    search = 'tab=audit-log&section=settings';
    render(<AuditLogTab />);
    expect(screen.getByTestId('retention')).toBeInTheDocument();
    expect(screen.getByTestId('exports')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Events' }));
    expect(mockPush).toHaveBeenCalledWith('?tab=audit-log&section=events', {
      scroll: false,
    });
  });

  it.each(['exports', 'streaming', 'api'])(
    'opens the settings tab for the old %s section',
    section => {
      search = `section=${section}`;
      render(<AuditLogTab />);
      expect(screen.getByTestId('api')).toBeInTheDocument();
    }
  );

  it('leaves out the export card for a reader who cannot export', () => {
    allowed = new Set(['audit_log:read']);
    search = 'section=settings';
    render(<AuditLogTab />);
    expect(screen.getByTestId('retention')).toBeInTheDocument();
    expect(screen.queryByTestId('exports')).not.toBeInTheDocument();
  });

  it('shows streaming only to those who can manage the audit log', () => {
    search = 'section=settings';
    const { unmount } = render(<AuditLogTab />);
    expect(screen.queryByTestId('streaming')).not.toBeInTheDocument();
    unmount();

    allowed = new Set(['audit_log:read', 'audit_log:manage']);
    render(<AuditLogTab />);
    expect(screen.getByTestId('streaming')).toBeInTheDocument();
  });

  it('denies access without any audit log capability', () => {
    allowed = new Set();
    render(<AuditLogTab />);
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
    expect(screen.getByText(/view the audit log/i)).toBeInTheDocument();
    expect(mockGetSettings).not.toHaveBeenCalled();
  });

  it('waits for permissions before choosing a section', () => {
    loading = true;
    render(<AuditLogTab />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByTestId('events')).not.toBeInTheDocument();
  });
});
