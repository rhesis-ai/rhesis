import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TokensGrid from '../TokensGrid';

// Stub out BaseDataGrid to avoid full MUI DataGrid setup
jest.mock('@/components/common/BaseDataGrid', () => ({
  __esModule: true,
  default: ({
    rows,
    columns,
  }: {
    rows: { id: string; name: string }[];
    columns: {
      field: string;
      renderCell?: (p: {
        row: { id: string; name: string };
      }) => React.ReactNode;
    }[];
  }) => (
    <table>
      <thead>
        <tr>
          {columns.map((c: { field: string }) => (
            <th key={c.field}>{c.field}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row: { id: string; name: string }) => (
          <tr key={row.id}>
            {columns.map(
              (c: {
                field: string;
                renderCell?: (p: {
                  row: { id: string; name: string };
                }) => React.ReactNode;
              }) => (
                <td key={c.field}>
                  {c.renderCell
                    ? c.renderCell({ row })
                    : ((row as Record<string, unknown>)[
                        c.field
                      ] as React.ReactNode)}
                </td>
              )
            )}
          </tr>
        ))}
      </tbody>
    </table>
  ),
}));

jest.mock('../RefreshTokenModal', () => ({
  __esModule: true,
  default: ({ open, onClose }: { open: boolean; onClose: () => void }) =>
    open ? (
      <div data-testid="refresh-modal">
        <button onClick={onClose}>close-refresh</button>
      </div>
    ) : null,
}));

const onRefreshToken = jest.fn().mockResolvedValue(undefined);
const onDeleteToken = jest.fn().mockResolvedValue(undefined);
const onCreateToken = jest.fn();

function makeToken(id: string) {
  return {
    id,
    name: `Token ${id}`,
    token_obfuscated: `rhesis_****${id}`,
    last_used_at: null,
    expires_at: null,
    created_at: new Date().toISOString(),
  };
}

describe('TokensGrid', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows a loading spinner when loading=true and no tokens', () => {
    render(
      <TokensGrid
        tokens={[]}
        loading={true}
        onRefreshToken={onRefreshToken}
        onDeleteToken={onDeleteToken}
        totalCount={0}
      />
    );
    expect(
      document.querySelector('.MuiCircularProgress-root')
    ).toBeInTheDocument();
  });

  it('shows empty state when not loading and no tokens', () => {
    render(
      <TokensGrid
        tokens={[]}
        loading={false}
        onRefreshToken={onRefreshToken}
        onDeleteToken={onDeleteToken}
        totalCount={0}
      />
    );
    expect(screen.getByText(/no api tokens yet/i)).toBeInTheDocument();
  });

  it('renders a Create API Token button in the empty state', () => {
    render(
      <TokensGrid
        tokens={[]}
        loading={false}
        onRefreshToken={onRefreshToken}
        onDeleteToken={onDeleteToken}
        onCreateToken={onCreateToken}
        totalCount={0}
      />
    );
    const createBtns = screen.getAllByRole('button', {
      name: /create api token/i,
    });
    expect(createBtns.length).toBeGreaterThan(0);
  });

  it('calls onCreateToken when the empty state button is clicked', async () => {
    const user = userEvent.setup();
    render(
      <TokensGrid
        tokens={[]}
        loading={false}
        onRefreshToken={onRefreshToken}
        onDeleteToken={onDeleteToken}
        onCreateToken={onCreateToken}
        totalCount={0}
      />
    );
    const createBtns = screen.getAllByRole('button', {
      name: /create api token/i,
    });
    await user.click(createBtns[0]);
    expect(onCreateToken).toHaveBeenCalled();
  });

  it('renders token names in the data grid', () => {
    render(
      <TokensGrid
        tokens={[makeToken('t1'), makeToken('t2')]}
        loading={false}
        onRefreshToken={onRefreshToken}
        onDeleteToken={onDeleteToken}
        totalCount={2}
      />
    );
    expect(screen.getByText('Token t1')).toBeInTheDocument();
    expect(screen.getByText('Token t2')).toBeInTheDocument();
  });
});
