import React from 'react';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import BaseDataGrid, { applyFlexColumnSizing } from '../BaseDataGrid';
import { GridColDef, GridRowModel } from '@mui/x-data-grid';

// Lightweight stub for MUI DataGrid — renders rows as a plain HTML table so
// tests can query the data without needing the full virtualized grid.
jest.mock('@mui/x-data-grid', () => {
  const original = jest.requireActual('@mui/x-data-grid');

  const MockDataGrid = ({
    rows,
    columns,
    loading,
    getRowId,
    onRowClick,
  }: {
    rows: GridRowModel[];
    columns: GridColDef[];
    loading?: boolean;
    getRowId?: (row: GridRowModel) => string | number;
    onRowClick?: (params: { row: GridRowModel }) => void;
  }) => {
    if (loading) return <div data-testid="datagrid-loading">Loading…</div>;
    return (
      <table role="grid" data-testid="data-grid">
        <thead>
          <tr>
            {columns.map((col: GridColDef) => (
              <th key={String(col.field)}>
                {String(col.headerName ?? col.field)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row: GridRowModel) => {
            const rowKey = getRowId
              ? String(getRowId(row))
              : String(row.id ?? row);
            return (
              <tr
                key={rowKey}
                role="row"
                onClick={() => onRowClick && onRowClick({ row })}
                data-testid={`row-${rowKey}`}
              >
                {columns.map((col: GridColDef) => (
                  <td key={String(col.field)}>
                    {String(row[col.field] ?? '')}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  };

  return {
    ...original,
    DataGrid: MockDataGrid,
    useGridApiRef: () => ({ current: null }),
  };
});

const sampleColumns: GridColDef[] = [
  { field: 'id', headerName: 'ID' },
  { field: 'name', headerName: 'Name' },
  { field: 'status', headerName: 'Status' },
];

const sampleRows = [
  { id: '1', name: 'Alice', status: 'active' },
  { id: '2', name: 'Bob', status: 'inactive' },
  { id: '3', name: 'Charlie', status: 'active' },
];

describe('applyFlexColumnSizing', () => {
  it('promotes first non-fixed column to flex when no flex column exists', () => {
    const columns: GridColDef[] = [
      { field: 'title', headerName: 'Title', width: 300, minWidth: 150 },
      { field: 'status', headerName: 'Status', width: 120, minWidth: 90 },
      { field: 'actions', headerName: '', width: 88 },
    ];

    const sized = applyFlexColumnSizing(columns);

    expect(sized[0]).toMatchObject({ flex: 1, minWidth: 150 });
    expect(sized[0].maxWidth).toBeUndefined();
    expect(sized[1]).toMatchObject({ width: 120, maxWidth: 120, minWidth: 90 });
    expect(sized[1].flex).toBeUndefined();
    expect(sized[2]).toMatchObject({ width: 88, hideable: false });
    expect(sized[2].flex).toBeUndefined();
  });

  it('caps width-only columns when another column already has flex', () => {
    const columns: GridColDef[] = [
      { field: 'title', headerName: 'Title', width: 300, minWidth: 150 },
      { field: 'desc', headerName: 'Description' },
      { field: 'actions', headerName: '', width: 88 },
    ];

    const sized = applyFlexColumnSizing(columns);

    expect(sized[0]).toMatchObject({
      width: 300,
      maxWidth: 300,
      minWidth: 150,
    });
    expect(sized[0].flex).toBeUndefined();
    expect(sized[1]).toMatchObject({ flex: 1, minWidth: 50 });
    expect(sized[2]).toMatchObject({ width: 88, hideable: false });
  });

  it('gives unsized columns flex to fill remaining width', () => {
    const columns: GridColDef[] = [{ field: 'name', headerName: 'Name' }];

    expect(applyFlexColumnSizing(columns)[0]).toMatchObject({
      flex: 1,
      minWidth: 50,
    });
  });

  it('preserves columns that already define flex', () => {
    const columns: GridColDef[] = [
      { field: 'name', headerName: 'Name', flex: 2, minWidth: 100 },
    ];

    expect(applyFlexColumnSizing(columns)[0]).toEqual(columns[0]);
  });

  it('preserves columns with maxWidth as fixed-width', () => {
    const columns: GridColDef[] = [
      { field: 'name', headerName: 'Name', width: 200, maxWidth: 200 },
    ];

    expect(applyFlexColumnSizing(columns)[0]).toEqual(columns[0]);
  });
});

describe('BaseDataGrid', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runAllTimers();
    jest.useRealTimers();
  });

  function renderAndInit(ui: React.ReactElement) {
    const result = render(ui);
    // Flush the initialization setTimeout(0) inside BaseDataGrid and process
    // any resulting React state updates in a single synchronous act() call.
    act(() => {
      jest.runAllTimers();
    });
    return result;
  }

  describe('data grid rendering', () => {
    it('renders the data grid', () => {
      renderAndInit(<BaseDataGrid columns={sampleColumns} rows={sampleRows} />);
      expect(screen.getByRole('grid')).toBeInTheDocument();
    });

    it('shows loading indicator while loading prop is true', () => {
      renderAndInit(
        <BaseDataGrid columns={sampleColumns} rows={[]} loading={true} />
      );
      expect(screen.getByTestId('datagrid-loading')).toBeInTheDocument();
    });

    it('renders all row data', () => {
      renderAndInit(<BaseDataGrid columns={sampleColumns} rows={sampleRows} />);
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
      expect(screen.getByText('Charlie')).toBeInTheDocument();
    });

    it('renders column headers', () => {
      renderAndInit(<BaseDataGrid columns={sampleColumns} rows={sampleRows} />);
      expect(screen.getByText('Name')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
    });

    it('renders empty grid with no rows', () => {
      renderAndInit(<BaseDataGrid columns={sampleColumns} rows={[]} />);
      expect(screen.getByRole('grid')).toBeInTheDocument();
    });
  });

  it('introduces no button elements of its own', () => {
    // The DataGrid itself is mocked here (no built-in toolbar buttons), so
    // BaseDataGrid should render zero buttons around it.
    renderAndInit(<BaseDataGrid columns={sampleColumns} rows={sampleRows} />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  describe('row click', () => {
    it('calls onRowClick with the clicked row data', async () => {
      const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
      const onRowClick = jest.fn();
      renderAndInit(
        <BaseDataGrid
          columns={sampleColumns}
          rows={sampleRows}
          onRowClick={onRowClick}
        />
      );
      await user.click(screen.getByTestId('row-1'));
      expect(onRowClick).toHaveBeenCalledWith(
        expect.objectContaining({ row: sampleRows[0] })
      );
    });
  });

  describe('Paper wrapper', () => {
    it('wraps grid in Paper by default', () => {
      const { container } = renderAndInit(
        <BaseDataGrid columns={sampleColumns} rows={sampleRows} />
      );
      expect(container.querySelector('.MuiPaper-root')).toBeInTheDocument();
    });

    it('omits Paper wrapper when disablePaperWrapper=true', () => {
      const { container } = renderAndInit(
        <BaseDataGrid
          columns={sampleColumns}
          rows={sampleRows}
          disablePaperWrapper={true}
        />
      );
      expect(container.querySelector('.MuiPaper-root')).not.toBeInTheDocument();
    });
  });
});
