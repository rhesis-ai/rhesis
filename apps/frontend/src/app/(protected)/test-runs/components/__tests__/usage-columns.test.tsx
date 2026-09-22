import { render, screen } from '@testing-library/react';
import type { GridColDef } from '@mui/x-data-grid';
import {
  usageColumns,
  USAGE_COLUMNS_HIDDEN_BY_DEFAULT,
} from '../usage-columns';
import { gridSortToApiParams } from '@/utils/grid-sort';
import { formatCost } from '@/utils/trace-utils';
import type {
  TestRunDetail,
  TestRunUsage,
} from '@/utils/api-client/interfaces/test-run';
import { createMockTestRun } from '@/__mocks__/test-utils';

const ZERO_USAGE: TestRunUsage = {
  total_tokens: 0,
  total_input_tokens: 0,
  total_output_tokens: 0,
  total_cost_usd: 0,
  total_input_cost_usd: 0,
  total_output_cost_usd: 0,
  models: [],
  providers: [],
};

function runWith(usage?: Partial<TestRunUsage>): TestRunDetail {
  return createMockTestRun({
    id: 'run-1',
    usage: usage ? { ...ZERO_USAGE, ...usage } : undefined,
  }) as TestRunDetail;
}

const priced = runWith({
  total_tokens: 112743,
  total_input_tokens: 108965,
  total_output_tokens: 3778,
  total_cost_usd: 0.032791,
  total_input_cost_usd: 0.027225,
  total_output_cost_usd: 0.005566,
  models: ['gemini-3.1-flash-lite'],
  providers: ['gemini'],
});

function column(field: string): GridColDef {
  const found = usageColumns(formatCost).find(col => col.field === field);
  if (!found) throw new Error(`no column ${field}`);
  return found;
}

function renderCell(field: string, row: TestRunDetail) {
  const col = column(field);
  // valueGetter/renderCell are called directly rather than through a mounted grid:
  // these columns are pure formatting, and the DataGrid brings virtualisation that
  // makes assertions about a single cell far more fragile than the cell itself.
  const getValue = col.valueGetter as
    ((value: unknown, row: TestRunDetail) => unknown) | undefined;
  const value = getValue?.(undefined, row);
  const cell = col.renderCell as
    | ((params: { value: unknown; row: TestRunDetail }) => React.ReactNode)
    | undefined;
  return render(<>{cell?.({ value, row })}</>);
}

describe('usage columns', () => {
  it('adds the seven columns the traces grid also names', () => {
    expect(usageColumns(formatCost).map(col => col.headerName)).toEqual([
      'Tokens',
      'Input tokens',
      'Output tokens',
      'Cost',
      'Input cost',
      'Output cost',
      'Model',
    ]);
  });

  it('formats tokens and cost', () => {
    renderCell('usage.total_tokens', priced);
    expect(screen.getByText('112,743')).toBeInTheDocument();

    renderCell('usage.total_cost_usd', priced);
    expect(screen.getByText('$0.03')).toBeInTheDocument();
  });

  it('shows the split figures in their own columns', () => {
    renderCell('usage.total_input_tokens', priced);
    expect(screen.getByText('108,965')).toBeInTheDocument();

    renderCell('usage.total_output_cost_usd', priced);
    expect(screen.getByText('$0.0056')).toBeInTheDocument();
  });

  it('renders the model as provider/model', () => {
    renderCell('usage.models', priced);
    expect(
      screen.getByText('gemini/gemini-3.1-flash-lite')
    ).toBeInTheDocument();
  });

  it('counts the rest when a run used several models', () => {
    renderCell(
      'usage.models',
      runWith({ models: ['a', 'b', 'c'], providers: ['openai'] })
    );
    expect(screen.getByText('openai/a +2')).toBeInTheDocument();
  });

  it('shows a dash rather than a zero for a run that traced nothing', () => {
    // Zero cost and "no traces" are different claims; models is what separates them.
    renderCell('usage.total_cost_usd', runWith({ models: [] }));
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('survives a row with no usage block at all', () => {
    renderCell('usage.total_tokens', runWith());
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('still renders a genuine zero for a run that traced something unpriced', () => {
    renderCell(
      'usage.total_cost_usd',
      runWith({ models: ['self-hosted'], providers: ['unknown'] })
    );
    expect(screen.getByText('$0.00')).toBeInTheDocument();
  });

  it('leaves every column server-sortable', () => {
    // sortable defaults to true; an explicit false would silently drop the deep sort.
    expect(usageColumns(formatCost).every(col => col.sortable !== false)).toBe(
      true
    );
  });

  it('maps every column to a sort field the API accepts', () => {
    const apiFields = usageColumns(formatCost).map(
      col => gridSortToApiParams([{ field: col.field, sort: 'desc' }]).sort_by
    );

    expect(apiFields).toEqual([
      'total_tokens',
      'total_input_tokens',
      'total_output_tokens',
      'total_cost_usd',
      'total_input_cost_usd',
      'total_output_cost_usd',
      'model',
    ]);
  });

  it('hides only the four split columns by default', () => {
    expect(Object.keys(USAGE_COLUMNS_HIDDEN_BY_DEFAULT).sort()).toEqual([
      'usage.total_input_cost_usd',
      'usage.total_input_tokens',
      'usage.total_output_cost_usd',
      'usage.total_output_tokens',
    ]);
    expect(
      Object.values(USAGE_COLUMNS_HIDDEN_BY_DEFAULT).every(v => v === false)
    ).toBe(true);
  });
});
