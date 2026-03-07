import React from 'react';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import BaseDataGrid from '../BaseDataGrid';
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

  describe('title', () => {
    it('renders title when provided', () => {
      renderAndInit(
        <BaseDataGrid
          columns={sampleColumns}
          rows={sampleRows}
          title="My Grid"
        />
      );
      expect(
        screen.getByRole('heading', { name: 'My Grid' })
      ).toBeInTheDocument();
    });

    it('does not render a heading when title is omitted', () => {
      renderAndInit(<BaseDataGrid columns={sampleColumns} rows={sampleRows} />);
      expect(screen.queryByRole('heading')).not.toBeInTheDocument();
    });
  });

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

  describe('action buttons', () => {
    it('renders a simple action button', () => {
      const onClick = jest.fn();
      renderAndInit(
        <BaseDataGrid
          columns={sampleColumns}
          rows={sampleRows}
          actionButtons={[{ label: 'Add Item', onClick }]}
        />
      );
      expect(
        screen.getByRole('button', { name: /add item/i })
      ).toBeInTheDocument();
    });

    it('calls onClick when action button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
      const onClick = jest.fn();
      renderAndInit(
        <BaseDataGrid
          columns={sampleColumns}
          rows={sampleRows}
          actionButtons={[{ label: 'Add Item', onClick }]}
        />
      );
      await user.click(screen.getByRole('button', { name: /add item/i }));
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('renders disabled action button when disabled=true', () => {
      renderAndInit(
        <BaseDataGrid
          columns={sampleColumns}
          rows={sampleRows}
          actionButtons={[
            { label: 'Locked', onClick: jest.fn(), disabled: true },
          ]}
        />
      );
      expect(screen.getByRole('button', { name: /locked/i })).toBeDisabled();
    });

    it('renders multiple action buttons', () => {
      renderAndInit(
        <BaseDataGrid
          columns={sampleColumns}
          rows={sampleRows}
          actionButtons={[
            { label: 'Add', onClick: jest.fn() },
            { label: 'Export', onClick: jest.fn() },
          ]}
        />
      );
      expect(
        screen.getByRole('button', { name: /^add$/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /export/i })
      ).toBeInTheDocument();
    });

    it('does not inject action buttons when actionButtons prop is omitted', () => {
      renderAndInit(<BaseDataGrid columns={sampleColumns} rows={sampleRows} />);
      // BaseDataGrid only renders action-button elements when the actionButtons
      // prop is supplied.  The DataGrid itself is mocked here (no built-in
      // toolbar/quick-filter buttons), so we can assert that the component
      // introduces no button elements of its own when no actions are requested.
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
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

  describe('dropdown filters', () => {
    const filters = [
      {
        name: 'status',
        label: 'Status',
        filterField: 'status',
        defaultValue: 'all',
        options: [
          { value: 'all', label: 'All' },
          { value: 'active', label: 'Active' },
          { value: 'inactive', label: 'Inactive' },
        ],
      },
    ];

    it('renders a filter dropdown when filters are provided', () => {
      renderAndInit(
        <BaseDataGrid
          columns={sampleColumns}
          rows={sampleRows}
          filters={filters}
        />
      );
      expect(screen.getByLabelText(/status/i)).toBeInTheDocument();
    });

    it('shows all rows when filter default is "all"', () => {
      renderAndInit(
        <BaseDataGrid
          columns={sampleColumns}
          rows={sampleRows}
          filters={filters}
        />
      );
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
      expect(screen.getByText('Charlie')).toBeInTheDocument();
    });
  });

  describe('custom toolbar content', () => {
    it('renders custom toolbar content', () => {
      renderAndInit(
        <BaseDataGrid
          columns={sampleColumns}
          rows={sampleRows}
          customToolbarContent={<div data-testid="custom-toolbar">Custom</div>}
        />
      );
      expect(screen.getByTestId('custom-toolbar')).toBeInTheDocument();
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
