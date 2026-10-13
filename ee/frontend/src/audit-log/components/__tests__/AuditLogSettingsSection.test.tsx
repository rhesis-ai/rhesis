/**
 * Retention and privacy settings: loading and error states, read-only for a
 * role without `audit_log:manage` (the Auditor), the plan cap's 422, and the
 * EU AI Act and scheduler warnings.
 */

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AuditLogSettingsSection from '../AuditLogSettingsSection';
import type { AuditLogSettings } from '../../types';

let canManage = true;

jest.mock('@/components/common/Can', () => ({
  useCan: (capability: string) =>
    capability === 'audit_log:manage' ? canManage : true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

const mockGetSettings = jest.fn();
const mockUpdateSettings = jest.fn();

jest.mock('../../api/audit-log-client', () => ({
  ...jest.requireActual('../../api/audit-log-client'),
  AuditLogClient: jest.fn().mockImplementation(() => ({
    getSettings: mockGetSettings,
    updateSettings: mockUpdateSettings,
  })),
}));

function settings(overrides: Partial<AuditLogSettings> = {}): AuditLogSettings {
  return {
    retention_days: 365,
    max_retention_days: 365,
    below_eu_ai_act_minimum: false,
    mask_ip: true,
    include_content: false,
    scheduled_jobs_running: true,
    ...overrides,
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  canManage = true;
  mockGetSettings.mockResolvedValue(settings());
});

describe('AuditLogSettingsSection', () => {
  it('shows a spinner while loading', () => {
    mockGetSettings.mockReturnValue(new Promise(() => {}));
    render(<AuditLogSettingsSection />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows the error when the settings cannot load', async () => {
    mockGetSettings.mockRejectedValue(new Error('API error: 500 - Boom'));
    render(<AuditLogSettingsSection />);
    expect(await screen.findByText('Boom')).toBeInTheDocument();
  });

  it('shows the saved values, with secrets always redacted', async () => {
    render(<AuditLogSettingsSection />);
    expect(await screen.findByLabelText('1 year')).toBeChecked();
    expect(screen.getByLabelText('Mask IP addresses')).toBeChecked();
    expect(screen.getByLabelText('Include content')).not.toBeChecked();
    const redact = screen.getByLabelText('Redact secrets');
    expect(redact).toBeChecked();
    expect(redact).toBeDisabled();
    expect(
      screen.getByText(/keeps events for up to 1 year/)
    ).toBeInTheDocument();
  });

  it('is read-only without audit_log:manage', async () => {
    canManage = false;
    render(<AuditLogSettingsSection />);
    expect(await screen.findByLabelText('1 year')).toBeDisabled();
    expect(screen.getByLabelText('Mask IP addresses')).toBeDisabled();
    expect(screen.getByLabelText('Include content')).toBeDisabled();
    expect(
      screen.queryByRole('button', { name: 'Save retention' })
    ).not.toBeInTheDocument();
    expect(screen.getByText(/You can view these settings/)).toBeInTheDocument();
  });

  it('saves a preset and shows the 422 above the plan cap', async () => {
    mockUpdateSettings.mockRejectedValue(
      new Error(
        'API error: 422 - retention_days can be at most 365 on this plan'
      )
    );
    render(<AuditLogSettingsSection />);
    fireEvent.click(await screen.findByLabelText('3 years'));
    fireEvent.click(screen.getByRole('button', { name: 'Save retention' }));

    expect(
      await screen.findByText('retention_days can be at most 365 on this plan')
    ).toBeInTheDocument();
    expect(mockUpdateSettings).toHaveBeenCalledWith({ retention_days: 1095 });
  });

  it('takes a custom value in range only', async () => {
    mockUpdateSettings.mockResolvedValue(settings({ retention_days: 200 }));
    render(<AuditLogSettingsSection />);
    fireEvent.click(await screen.findByLabelText('Custom'));
    const days = screen.getByLabelText('Days');
    const save = screen.getByRole('button', { name: 'Save retention' });

    fireEvent.change(days, { target: { value: '30' } });
    expect(save).toBeDisabled();

    fireEvent.change(days, { target: { value: '200' } });
    fireEvent.click(save);
    await waitFor(() =>
      expect(mockUpdateSettings).toHaveBeenCalledWith({ retention_days: 200 })
    );
  });

  it('saves a privacy toggle at once', async () => {
    mockUpdateSettings.mockResolvedValue(settings({ mask_ip: false }));
    render(<AuditLogSettingsSection />);
    fireEvent.click(await screen.findByLabelText('Mask IP addresses'));
    await waitFor(() =>
      expect(mockUpdateSettings).toHaveBeenCalledWith({ mask_ip: false })
    );
    expect(
      screen.getByText(/events already recorded stay masked/)
    ).toBeInTheDocument();
  });

  it('warns, without blocking, below the EU AI Act minimum', async () => {
    mockGetSettings.mockResolvedValue(
      settings({ retention_days: 90, below_eu_ai_act_minimum: true })
    );
    render(<AuditLogSettingsSection />);
    expect(await screen.findByText(/EU AI Act/)).toBeInTheDocument();
  });

  it('warns when scheduled jobs are not running', async () => {
    mockGetSettings.mockResolvedValue(
      settings({ scheduled_jobs_running: false })
    );
    render(<AuditLogSettingsSection />);
    expect(
      await screen.findByText(/Scheduled jobs are not running/)
    ).toBeInTheDocument();
  });

  it('says nothing about scheduled jobs when the backend cannot tell', async () => {
    mockGetSettings.mockResolvedValue(
      settings({ scheduled_jobs_running: null })
    );
    render(<AuditLogSettingsSection />);
    await screen.findByLabelText('1 year');
    expect(
      screen.queryByText(/Scheduled jobs are not running/)
    ).not.toBeInTheDocument();
  });
});
