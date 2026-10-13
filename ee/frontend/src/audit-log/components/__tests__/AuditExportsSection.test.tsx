/**
 * The Exports section: the signed-in user's export jobs from the Jobs API,
 * Download only once a job has completed, and the format dialog.
 */

import React from 'react';
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import AuditExportDialog from '../AuditExportDialog';
import AuditExportsSection from '../AuditExportsSection';
import type { Job } from '@/utils/api-client/interfaces/job';

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'u1', name: 'Alice' } },
    status: 'authenticated',
  }),
}));

const mockShow = jest.fn();
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockShow, close: jest.fn() }),
}));

const mockGetJobs = jest.fn();
jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getJobsClient: () => ({ getJobs: mockGetJobs }),
  })),
}));

const mockCreateExport = jest.fn();
jest.mock('../../api/audit-log-client', () => ({
  ...jest.requireActual('../../api/audit-log-client'),
  AuditLogClient: jest.fn().mockImplementation(() => ({
    createExport: mockCreateExport,
    exportDownloadUrl: (id: string) => `/api/backend/download/${id}`,
  })),
}));

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: 'j1',
    job_type: 'audit_log.export',
    status: 'completed',
    attempt: 1,
    created_at: '2026-10-13T10:00:00Z',
    updated_at: '2026-10-13T10:01:00Z',
    is_terminal: true,
    cancellable: false,
    job_metadata: { format: 'csv', filter: null },
    ...overrides,
  };
}

function rowOf(text: string): HTMLElement {
  const row = screen.getByText(text).closest('tr');
  if (!row) throw new Error(`no row for ${text}`);
  return row;
}

beforeEach(() => {
  jest.clearAllMocks();
  mockGetJobs.mockResolvedValue({ data: [] });
});

describe('AuditExportsSection', () => {
  it("asks the Jobs API for this user's export jobs only", async () => {
    render(<AuditExportsSection />);
    expect(await screen.findByText('No exports yet')).toBeInTheDocument();
    expect(mockGetJobs).toHaveBeenCalledWith(
      expect.objectContaining({
        sort_by: 'created_at',
        sort_order: 'desc',
        $filter: "job_type eq 'audit_log.export' and user_id eq u1",
      })
    );
  });

  it('shows the error when the jobs cannot load', async () => {
    mockGetJobs.mockRejectedValue(new Error('API error: 500 - Jobs down'));
    render(<AuditExportsSection />);
    expect(await screen.findByText('Jobs down')).toBeInTheDocument();
  });

  it('links a completed export to its download, and holds back an unfinished one', async () => {
    mockGetJobs.mockResolvedValue({
      data: [
        job(),
        job({
          id: 'j2',
          status: 'running',
          is_terminal: false,
          progress_current: 50,
          progress_total: 200,
          job_metadata: { format: 'jsonl', filter: "outcome eq 'denied'" },
        }),
      ],
    });
    render(<AuditExportsSection />);

    const done = (await screen.findByText('CSV')).closest('tr');
    if (!done) throw new Error('no row');
    expect(
      within(done).getByRole('link', { name: /Download/ })
    ).toHaveAttribute('href', '/api/backend/download/j1');
    expect(within(done).getByText('All events')).toBeInTheDocument();

    const running = rowOf('JSONL');
    expect(within(running).getByText('Running 25%')).toBeInTheDocument();
    expect(within(running).getByText('Filtered')).toBeInTheDocument();
    // Not a link until the job completes, so no 409 from the backend.
    expect(
      within(running).queryByRole('link', { name: /Download/ })
    ).not.toBeInTheDocument();
    expect(
      within(running).getByRole('button', { name: /Download/ })
    ).toBeDisabled();
    expect(
      within(running).getByRole('link', { name: 'View job' })
    ).toHaveAttribute('href', '/jobs/j2');
  });

  it('offers no download once the file has been cleaned up', async () => {
    mockGetJobs.mockResolvedValue({
      data: [
        job({
          job_metadata: {
            format: 'csv',
            filter: null,
            file_deleted_at: '2026-10-20T05:00:00Z',
          },
        }),
      ],
    });
    render(<AuditExportsSection />);

    await screen.findByText('CSV');
    const row = rowOf('CSV');
    expect(
      within(row).queryByRole('link', { name: /Download/ })
    ).not.toBeInTheDocument();
    expect(within(row).getByRole('button', { name: 'Expired' })).toBeDisabled();
  });

  it('exports the whole log in the chosen format', async () => {
    mockCreateExport.mockResolvedValue({
      job_id: 'j3',
      task_id: 't3',
      format: 'csv',
      message: '',
    });
    render(<AuditExportsSection />);
    await screen.findByText('No exports yet');

    fireEvent.click(screen.getByRole('button', { name: /Export all events/ }));
    fireEvent.click(screen.getByLabelText(/CSV/));
    fireEvent.click(screen.getByRole('button', { name: 'Export' }));

    await waitFor(() =>
      expect(mockCreateExport).toHaveBeenCalledWith({ format: 'csv' })
    );
    await waitFor(() => expect(mockShow).toHaveBeenCalled());
    // The list refetches so the new job shows up.
    await waitFor(() => expect(mockGetJobs).toHaveBeenCalledTimes(2));
  });

  it("sends the Events list's filter when started from its toolbar", async () => {
    mockCreateExport.mockResolvedValue({
      job_id: 'j4',
      task_id: 't4',
      format: 'jsonl',
      message: '',
    });
    const onClose = jest.fn();
    render(
      <AuditExportDialog open onClose={onClose} filter="outcome eq 'denied'" />
    );
    expect(screen.getByText(/matches the current search/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Export' }));
    await waitFor(() =>
      expect(mockCreateExport).toHaveBeenCalledWith({
        format: 'jsonl',
        filter: "outcome eq 'denied'",
      })
    );
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('keeps the dialog open with the error when the export cannot start', async () => {
    mockCreateExport.mockRejectedValue(
      new Error('API error: 400 - Invalid filter')
    );
    render(<AuditExportsSection />);
    await screen.findByText('No exports yet');

    fireEvent.click(screen.getByRole('button', { name: /Export all events/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Export' }));

    expect(await screen.findByText('Invalid filter')).toBeInTheDocument();
    expect(mockCreateExport).toHaveBeenCalledWith({ format: 'jsonl' });
  });
});
