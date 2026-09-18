'use client';

import React from 'react';
import { GridColDef } from '@mui/x-data-grid';
import ModelLabel from '@/components/common/ModelLabel';
import UsageCell from '@/components/common/UsageCell';
import { formatTokenCount } from '@/utils/trace-utils';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

/**
 * The usage columns on the test runs grid.
 *
 * Headers match the traces grid, so the same figure is called the same thing wherever it
 * appears. Every one is server-sorted through `usage.*` entries in `grid-sort.ts`, which
 * order the whole organization's runs rather than the page on screen.
 */

/** Shown until the user turns them on: seven more visible columns is unreadable. */
export const USAGE_COLUMNS_HIDDEN_BY_DEFAULT = {
  'usage.total_input_tokens': false,
  'usage.total_output_tokens': false,
  'usage.total_input_cost_usd': false,
  'usage.total_output_cost_usd': false,
} as const;

type UsageKey = keyof NonNullable<TestRunDetail['usage']>;

/**
 * A run that traced nothing shows a dash rather than a zero, because "we have no traces
 * for this" and "this cost nothing" are different claims. `models` is what tells them
 * apart: it is empty only when nothing was traced or priced.
 */
function hasUsage(row: TestRunDetail): boolean {
  return (row.usage?.models?.length ?? 0) > 0;
}

function numericColumn(
  field: UsageKey,
  headerName: string,
  format: (value: number) => string,
  tooltip: (row: TestRunDetail) => string | undefined
): GridColDef {
  return {
    field: `usage.${field}`,
    headerName,
    flex: 1.1,
    minWidth: 90,
    align: 'right',
    headerAlign: 'right',
    filterable: false,
    valueGetter: (_, row: TestRunDetail) => row.usage?.[field] ?? null,
    renderCell: params => {
      const row = params.row as TestRunDetail;
      // The run rollup zero-fills a run it found no traces for, so the "nothing traced"
      // case has to be recognised here rather than read off the number. The traces grid
      // needs no equivalent: its rows carry null for a figure nobody knows.
      return (
        <UsageCell
          value={hasUsage(row) ? (params.value as number | null) : null}
          format={format}
          title={tooltip(row)}
        />
      );
    },
  };
}

/** `formatMoney` with a currency already bound; see `utils/money.ts`. */
type MoneyFormatter = (amountUsd: number) => string;

function tokenSplit(row: TestRunDetail): string | undefined {
  const usage = row.usage;
  if (!usage) return undefined;
  return `${formatTokenCount(usage.total_input_tokens)} input · ${formatTokenCount(
    usage.total_output_tokens
  )} output`;
}

function costSplit(
  row: TestRunDetail,
  money: MoneyFormatter
): string | undefined {
  const usage = row.usage;
  if (!usage) return undefined;
  return `${money(usage.total_input_cost_usd)} input · ${money(
    usage.total_output_cost_usd
  )} output`;
}

/**
 * The usage columns, formatting money in whatever currency was chosen.
 *
 * Takes the formatter rather than reading it from a context: this builds column
 * definitions outside a component, so there is no hook to call. `TestRunsGrid`
 * holds the context and passes it down.
 */
export function usageColumns(money: MoneyFormatter): GridColDef[] {
  const cost = (row: TestRunDetail) => costSplit(row, money);
  return [
    numericColumn('total_tokens', 'Tokens', formatTokenCount, tokenSplit),
    numericColumn(
      'total_input_tokens',
      'Input tokens',
      formatTokenCount,
      tokenSplit
    ),
    numericColumn(
      'total_output_tokens',
      'Output tokens',
      formatTokenCount,
      tokenSplit
    ),
    numericColumn('total_cost_usd', 'Cost', money, cost),
    numericColumn('total_input_cost_usd', 'Input cost', money, cost),
    numericColumn('total_output_cost_usd', 'Output cost', money, cost),
    {
      field: 'usage.models',
      headerName: 'Model',
      flex: 1.6,
      minWidth: 120,
      filterable: false,
      // Sorted by the run's alphabetically first model, which is the one shown here.
      valueGetter: (_, row: TestRunDetail) => row.usage?.models?.[0] ?? null,
      renderCell: params => {
        const usage = (params.row as TestRunDetail).usage;
        return (
          <ModelLabel models={usage?.models} providers={usage?.providers} />
        );
      },
    },
  ];
}
