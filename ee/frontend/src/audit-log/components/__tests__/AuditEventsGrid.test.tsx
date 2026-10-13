/**
 * The Events table and its detail drawer, against a mocked audit client:
 * empty, loading and error states, server pagination params, and the drawer's
 * related events and "Open resource" link.
 */

import React from 'react';
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import type { GridColDef } from '@mui/x-data-grid';
import AuditEventsGrid from '../AuditEventsGrid';
import type { AuditEvent } from '../../types';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), refresh: jest.fn() }),
  usePathname: () => '/organizations/settings',
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'u1', name: 'Alice' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn(), close: jest.fn() }),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/hooks/useEndpoints', () => ({
  useProjects: () => ({ data: [{ id: 'p1', name: 'Travel Assistant' }] }),
}));

const mockListEvents = jest.fn();
const mockGetEvent = jest.fn();

jest.mock('../../api/audit-log-client', () => ({
  ...jest.requireActual('../../api/audit-log-client'),
  AuditLogClient: jest.fn().mockImplementation(() => ({
    listEvents: mockListEvents,
    getEvent: mockGetEvent,
    listActions: jest.fn().mockResolvedValue([]),
  })),
}));

jest.mock('@/components/common/BaseDataGrid', () => ({
  __esModule: true,
  GRID_PAPER_SX: {},
  default: function MockBaseDataGrid({
    rows,
    columns,
    loading,
    onRowClick,
  }: {
    rows: Array<Record<string, unknown>>;
    columns: GridColDef[];
    loading?: boolean;
    onRowClick?: (params: { id: unknown; row: unknown }) => void;
  }) {
    if (loading) return <div data-testid="grid-loading" />;
    return (
      <div data-testid="base-data-grid">
        {rows.map(row => (
          <div key={String(row.id)} data-testid={`row-${row.id}`}>
            {columns.map(col => (
              <div key={col.field}>{col.renderCell?.({ row } as never)}</div>
            ))}
            <button onClick={() => onRowClick?.({ id: row.id, row })}>
              open {String(row.id)}
            </button>
          </div>
        ))}
      </div>
    );
  },
}));

function page(data: AuditEvent[], total = data.length) {
  return {
    data,
    pagination: {
      totalCount: total,
      skip: 0,
      limit: 25,
      currentPage: 0,
      pageSize: 25,
      totalPages: Math.ceil(total / 25),
    },
  };
}

function makeEvent(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: 'e1',
    organization_id: 'o1',
    project_id: 'p1',
    occurred_at: '2026-10-05T12:00:00Z',
    recorded_at: '2026-10-05T12:00:00Z',
    action: 'endpoint.updated',
    outcome: 'success',
    status_code: null,
    actor_type: 'user',
    actor_id: 'u1',
    actor_credential_id: null,
    actor_credential_hint: null,
    actor_label: 'Harry Cruz <harry@example.com>',
    channel: 'mcp',
    ip: null,
    user_agent: null,
    resource_id: 'r1',
    resource_label: 'travel-agent-prod',
    request_id: 'req-1',
    trace_id: 'trace-1',
    span_id: 's1',
    job_id: null,
    changes: [{ field: 'temperature', kind: 'value', before: 0.7, after: 0.2 }],
    ...overrides,
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  mockListEvents.mockResolvedValue(page([makeEvent()], 60));
});

describe('AuditEventsGrid', () => {
  it('shows a spinner while the first page loads', () => {
    mockListEvents.mockReturnValue(new Promise(() => {}));
    render(<AuditEventsGrid />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows the empty state when the log has no events', async () => {
    mockListEvents.mockResolvedValue(page([]));
    render(<AuditEventsGrid />);
    expect(await screen.findByText('No events yet')).toBeInTheDocument();
  });

  it('shows the error when the list fails', async () => {
    mockListEvents.mockRejectedValue(new Error('Audit log unavailable'));
    render(<AuditEventsGrid />);
    expect(
      await screen.findByText(/Audit log unavailable/)
    ).toBeInTheDocument();
  });

  it('asks for the newest page on occurred_at and renders the row', async () => {
    render(<AuditEventsGrid />);
    const row = await screen.findByTestId('row-e1');
    expect(mockListEvents).toHaveBeenCalledWith(
      expect.objectContaining({
        skip: 0,
        limit: 25,
        sort_by: 'occurred_at',
        sort_order: 'desc',
      })
    );
    expect(within(row).getByText('Endpoint updated')).toBeInTheDocument();
    expect(within(row).getByText('Harry Cruz')).toBeInTheDocument();
    expect(within(row).getByText('Travel Assistant')).toBeInTheDocument();
    expect(within(row).getByText('MCP')).toBeInTheDocument();
    expect(within(row).getByText('temperature: 0.7 → 0.2')).toBeInTheDocument();
  });

  it('opens the drawer with related events and the resource link', async () => {
    const related = makeEvent({
      id: 'e2',
      action: 'metric.updated',
      resource_label: 'Refusal Detection',
    });
    mockGetEvent.mockResolvedValue(makeEvent());
    render(<AuditEventsGrid />);
    await screen.findByTestId('row-e1');

    mockListEvents.mockResolvedValue(page([makeEvent(), related]));
    fireEvent.click(screen.getByRole('button', { name: 'open e1' }));

    expect(await screen.findByText('req-1')).toBeInTheDocument();
    expect(mockGetEvent).toHaveBeenCalledWith('e1');
    await waitFor(() =>
      expect(mockListEvents).toHaveBeenCalledWith(
        expect.objectContaining({ $filter: "trace_id eq 'trace-1'" })
      )
    );
    expect(await screen.findByText('Metric updated')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open Endpoint/ })).toHaveAttribute(
      'href',
      '/endpoints/r1'
    );
  });
});
