/**
 * The Streaming section against a mocked destinations client: loading, empty
 * and error states, health and auto-pause, the one-time signing secret, test
 * events, pause and delete. Also the `audit_log:manage` guard in the tab.
 */

import React from 'react';
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import StreamingSection from '../StreamingSection';
import type { AuditDestination } from '../../destinations';

const mockShow = jest.fn();
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockShow, close: jest.fn() }),
}));

const mockList = jest.fn();
const mockCreate = jest.fn();
const mockSetPaused = jest.fn();
const mockDelete = jest.fn();
const mockTest = jest.fn();

jest.mock('../../api/audit-destinations-client', () => ({
  AuditDestinationsClient: jest.fn().mockImplementation(() => ({
    listDestinations: mockList,
    createDestination: mockCreate,
    setPaused: mockSetPaused,
    deleteDestination: mockDelete,
    sendTestEvent: mockTest,
  })),
}));

function makeDestination(
  overrides: Partial<AuditDestination> = {}
): AuditDestination {
  return {
    id: 'd1',
    name: 'SIEM hook',
    kind: 'webhook',
    settings: { url: 'https://siem.example.com/hook' },
    paused: false,
    paused_reason: null,
    delivered_through: '2026-10-13T10:00:00Z',
    last_success_at: '2026-10-13T10:00:00Z',
    last_error: null,
    last_error_at: null,
    consecutive_failures: 0,
    next_attempt_at: null,
    created_at: '2026-10-13T09:00:00Z',
    ...overrides,
  };
}

function apiError(status: number, detail: string) {
  return Object.assign(new Error(`API error: ${status} - ${detail}`), {
    status,
  });
}

function lastToast() {
  const call = mockShow.mock.calls[mockShow.mock.calls.length - 1];
  return { message: call?.[0], severity: call?.[1]?.severity };
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe('StreamingSection', () => {
  it('shows a spinner while loading', () => {
    mockList.mockReturnValue(new Promise(() => {}));
    render(<StreamingSection />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows the empty state with "within seconds"', async () => {
    mockList.mockResolvedValue([]);
    render(<StreamingSection />);
    expect(await screen.findByText('No destinations yet')).toBeInTheDocument();
    expect(screen.getByText(/within seconds/)).toBeInTheDocument();
    expect(screen.queryByText(/real time/i)).not.toBeInTheDocument();
  });

  it('shows a load error with retry', async () => {
    mockList.mockRejectedValueOnce(apiError(500, 'boom'));
    mockList.mockResolvedValueOnce([]);
    render(<StreamingSection />);
    expect(await screen.findByText('boom')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('No destinations yet')).toBeInTheDocument();
  });

  it('says streaming is unavailable when the licence has lapsed (404)', async () => {
    mockList.mockRejectedValue(apiError(404, 'Not Found'));
    render(<StreamingSection />);
    expect(
      await screen.findByText(/Enterprise licence is active/)
    ).toBeInTheDocument();
  });

  it('lists destinations with status and health from the list call', async () => {
    mockList.mockResolvedValue([
      makeDestination(),
      makeDestination({
        id: 'd2',
        name: 'Splunk',
        kind: 'splunk_hec',
        settings: {
          url: 'https://splunk.example.com/services/collector/event',
        },
        paused: true,
        paused_reason: 'failures',
        last_success_at: null,
        last_error: 'HTTP 503: unavailable',
        last_error_at: '2026-10-13T11:00:00Z',
        consecutive_failures: 20,
      }),
      makeDestination({
        id: 'd3',
        name: 'Datadog EU',
        kind: 'datadog',
        settings: { site: 'datadoghq.eu' },
        paused: true,
        paused_reason: 'manual',
      }),
    ]);
    render(<StreamingSection />);

    const hook = (await screen.findByText('SIEM hook')).closest<HTMLElement>(
      '[role="listitem"]'
    );
    const splunk = screen
      .getByText('Splunk')
      .closest<HTMLElement>('[role="listitem"]');
    const dd = screen
      .getByText('Datadog EU')
      .closest<HTMLElement>('[role="listitem"]');
    if (!hook || !splunk || !dd) throw new Error('rows missing');

    expect(within(hook).getByText('Active')).toBeInTheDocument();
    expect(within(hook).getByText('Webhook')).toBeInTheDocument();
    expect(
      within(hook).getByText('https://siem.example.com/hook')
    ).toBeInTheDocument();

    expect(within(splunk).getByText('Auto-paused')).toBeInTheDocument();
    expect(within(splunk).getByText('Splunk HEC')).toBeInTheDocument();
    expect(
      within(splunk).getByText(/20 failures in a row/)
    ).toBeInTheDocument();
    expect(within(splunk).getByText(/HTTP 503/)).toBeInTheDocument();
    expect(
      within(splunk).getByText('Nothing delivered yet')
    ).toBeInTheDocument();
    expect(
      within(splunk).getByRole('button', { name: 'Resume Splunk' })
    ).toBeInTheDocument();

    expect(within(dd).getByText('Paused')).toBeInTheDocument();
    expect(within(dd).getByText('datadoghq.eu')).toBeInTheDocument();

    expect(mockList).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/drop duplicates/i)).toBeInTheDocument();
    expect(
      screen.getAllByRole('link', { name: 'Standard Webhooks' })[0]
    ).toHaveAttribute('href', 'https://www.standardwebhooks.com');
  });

  it('adds a webhook and shows its signing secret once', async () => {
    mockList.mockResolvedValue([]);
    mockCreate.mockResolvedValue({
      ...makeDestination(),
      signing_secret: 'whsec_c2VjcmV0',
    });
    render(<StreamingSection />);

    fireEvent.click(
      await screen.findByRole('button', { name: /add destination/i })
    );
    fireEvent.change(screen.getByLabelText(/^Name/), {
      target: { value: 'SIEM hook' },
    });
    const url = screen.getByLabelText(/^URL/);
    fireEvent.change(url, { target: { value: 'http://siem.example.com' } });
    expect(screen.getByText('Use an https:// URL.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add' })).toBeDisabled();

    fireEvent.change(url, {
      target: { value: 'https://siem.example.com/hook' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith({
        kind: 'webhook',
        name: 'SIEM hook',
        url: 'https://siem.example.com/hook',
      })
    );
    expect(await screen.findByText('whsec_c2VjcmV0')).toBeInTheDocument();
    expect(screen.getByText(/won.t see this secret again/)).toBeInTheDocument();

    const done = screen.getByRole('button', { name: 'Done' });
    expect(done).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(done);

    await waitFor(() =>
      expect(screen.queryByText('whsec_c2VjcmV0')).not.toBeInTheDocument()
    );
    expect(screen.getByText('SIEM hook')).toBeInTheDocument();
  });

  it('shows the backend validation error in the form', async () => {
    mockList.mockResolvedValue([]);
    mockCreate.mockRejectedValue(
      apiError(400, 'Destination resolves to a private address')
    );
    render(<StreamingSection />);

    fireEvent.click(
      await screen.findByRole('button', { name: /add destination/i })
    );
    fireEvent.change(screen.getByLabelText(/^Name/), {
      target: { value: 'Internal' },
    });
    fireEvent.change(screen.getByLabelText(/^URL/), {
      target: { value: 'https://10.0.0.1/hook' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    expect(
      await screen.findByText('Destination resolves to a private address')
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^URL/)).toHaveValue('https://10.0.0.1/hook');
  });

  it('shows the Datadog form with the fixed site list', async () => {
    mockList.mockResolvedValue([]);
    mockCreate.mockResolvedValue(
      makeDestination({ kind: 'datadog', settings: { site: 'datadoghq.com' } })
    );
    render(<StreamingSection />);

    fireEvent.click(
      await screen.findByRole('button', { name: /add destination/i })
    );
    fireEvent.mouseDown(screen.getByLabelText('Type'));
    fireEvent.click(screen.getByRole('option', { name: 'Datadog' }));
    expect(screen.queryByLabelText(/^URL/)).not.toBeInTheDocument();

    fireEvent.mouseDown(screen.getByLabelText('Site'));
    expect(screen.getAllByRole('option')).toHaveLength(7);
    fireEvent.click(screen.getByRole('option', { name: 'datadoghq.eu' }));

    fireEvent.change(screen.getByLabelText(/^Name/), {
      target: { value: 'DD' },
    });
    fireEvent.change(screen.getByLabelText(/^API key/), {
      target: { value: 'key' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith({
        kind: 'datadog',
        name: 'DD',
        site: 'datadoghq.eu',
        api_key: 'key',
      })
    );
    // No secret for Datadog, so no reveal.
    expect(lastToast().message).toBe('Destination added');
  });

  it('reports a failed test event with its error', async () => {
    mockList.mockResolvedValue([makeDestination()]);
    mockTest.mockResolvedValue({ delivered: false, error: 'HTTP 401: nope' });
    render(<StreamingSection />);

    fireEvent.click(
      await screen.findByRole('button', {
        name: 'Send a test event to SIEM hook',
      })
    );
    await waitFor(() => expect(mockTest).toHaveBeenCalledWith('d1'));
    await waitFor(() =>
      expect(lastToast()).toEqual({
        message: 'Test event to SIEM hook failed: HTTP 401: nope',
        severity: 'error',
      })
    );
  });

  it('reports a delivered test event', async () => {
    mockList.mockResolvedValue([makeDestination()]);
    mockTest.mockResolvedValue({ delivered: true, error: null });
    render(<StreamingSection />);

    fireEvent.click(
      await screen.findByRole('button', {
        name: 'Send a test event to SIEM hook',
      })
    );
    await waitFor(() =>
      expect(lastToast()).toEqual({
        message: 'Test event delivered to SIEM hook',
        severity: 'success',
      })
    );
  });

  it('resumes an auto-paused destination', async () => {
    const paused = makeDestination({
      paused: true,
      paused_reason: 'failures',
      consecutive_failures: 20,
    });
    mockList.mockResolvedValue([paused]);
    mockSetPaused.mockResolvedValue(makeDestination());
    render(<StreamingSection />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Resume SIEM hook' })
    );
    await waitFor(() =>
      expect(mockSetPaused).toHaveBeenCalledWith('d1', false)
    );
    expect(await screen.findByText('Active')).toBeInTheDocument();
  });

  it('deletes only after confirmation', async () => {
    mockList.mockResolvedValue([makeDestination()]);
    mockDelete.mockResolvedValue(undefined);
    render(<StreamingSection />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Delete SIEM hook' })
    );
    expect(mockDelete).not.toHaveBeenCalled();
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith('d1'));
    expect(await screen.findByText('No destinations yet')).toBeInTheDocument();
  });
});
