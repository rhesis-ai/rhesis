/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import TracesClient from '../TracesClient';

const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace, push: jest.fn() }),
  usePathname: () => '/traces',
}));

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({ activeProject: { id: 'proj-1' }, loading: false }),
}));

const mockUseList = jest.fn();
jest.mock('@/hooks/useList', () => ({
  useList: (descriptor: any, options: any) => mockUseList(descriptor, options),
}));

const mockDrawerProps = jest.fn();
jest.mock('../TraceDrawer', () => ({
  __esModule: true,
  default: (props: any) => {
    mockDrawerProps(props);
    return null;
  },
}));

jest.mock('../TraceMetricsSummary', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('../TraceFilterDrawer', () => ({
  __esModule: true,
  default: () => null,
}));

// The real tables (and their toolbar) need a grid; these read the same toolbar
// context and offer the switch and one clickable row.
function MockSwitch() {
  const { TracesToolbarContext } = jest.requireActual('../TracesToolbar');
  const { onViewChange } = React.useContext(TracesToolbarContext) as any;
  if (!onViewChange) return null;
  return (
    <>
      <button onClick={() => onViewChange('traces')}>Traces</button>
      <button onClick={() => onViewChange('spans')}>Spans</button>
    </>
  );
}

jest.mock('../TracesTable', () => ({
  __esModule: true,
  default: ({ onRowClick }: any) => (
    <div>
      <MockSwitch />
      <button onClick={() => onRowClick('trace-9', 'proj-1')}>trace row</button>
    </div>
  ),
}));

jest.mock('../SpansTable', () => ({
  __esModule: true,
  default: ({ onRowClick }: any) => (
    <div>
      <MockSwitch />
      <button
        onClick={() =>
          onRowClick({
            trace_id: 'trace-1',
            project_id: 'proj-1',
            span_id: 'span-7',
          })
        }
      >
        span row
      </button>
    </div>
  ),
}));

function listResult() {
  return {
    data: [{ id: 'row' }],
    totalCount: 1,
    isLoading: false,
    error: null,
    refresh: jest.fn(),
    page: 0,
    rowsPerPage: 50,
    onPageChange: jest.fn(),
    onRowsPerPageChange: jest.fn(),
    sortModel: [],
    onSortModelChange: jest.fn(),
  };
}

function enabledLists(): string[] {
  const last = new Map<string, boolean>();
  mockUseList.mock.calls.forEach(([descriptor, options]) =>
    last.set(descriptor.resource, options.enabled)
  );
  return [...last].filter(([, enabled]) => enabled).map(([name]) => name);
}

function lastDrawerProps() {
  return mockDrawerProps.mock.calls[mockDrawerProps.mock.calls.length - 1][0];
}

beforeEach(() => {
  mockReplace.mockReset();
  mockUseList.mockReset();
  mockUseList.mockImplementation(listResult);
  mockDrawerProps.mockReset();
});

describe('TracesClient view switch', () => {
  it('starts on traces and fetches only traces', () => {
    render(<TracesClient />);

    expect(screen.getByText('trace row')).toBeInTheDocument();
    expect(enabledLists()).toEqual(['traces']);
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it('switches to spans, fetches spans and writes the view to the URL', () => {
    render(<TracesClient />);

    fireEvent.click(screen.getByRole('button', { name: 'Spans' }));

    expect(screen.getByText('span row')).toBeInTheDocument();
    expect(enabledLists()).toEqual(['spans']);
    expect(mockReplace).toHaveBeenLastCalledWith('/traces?view=spans', {
      scroll: false,
    });
  });

  it('opens on the view and filters it was given', () => {
    render(
      <TracesClient
        initialView="spans"
        initialFilters={{ timeRange: 'all', spanTypes: ['tool.invoke'] }}
      />
    );

    expect(screen.getByText('span row')).toBeInTheDocument();
    const spansCall = mockUseList.mock.calls.find(
      ([descriptor]) => descriptor.resource === 'spans'
    );
    expect(spansCall?.[1].filters.spanTypes).toEqual(['tool.invoke']);
  });

  it('keeps the URL alone on a test run', () => {
    render(<TracesClient fixedTestRunId="run-1" />);

    fireEvent.click(screen.getByRole('button', { name: 'Spans' }));

    expect(screen.getByText('span row')).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });
});

describe('TracesClient row click', () => {
  it('opens the drawer on the clicked span', () => {
    render(<TracesClient initialView="spans" />);

    fireEvent.click(screen.getByText('span row'));

    expect(lastDrawerProps()).toEqual(
      expect.objectContaining({
        open: true,
        traceId: 'trace-1',
        projectId: 'proj-1',
        initialSpanId: 'span-7',
      })
    );
  });

  it('opens a trace on its root, with no span picked', () => {
    render(<TracesClient />);

    fireEvent.click(screen.getByText('trace row'));

    expect(lastDrawerProps()).toEqual(
      expect.objectContaining({
        open: true,
        traceId: 'trace-9',
        initialSpanId: undefined,
      })
    );
  });
});
