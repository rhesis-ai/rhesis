'use client';

import React from 'react';
import { GridColDef } from '@mui/x-data-grid';
import { Tooltip, Typography } from '@mui/material';
import { formatCost, formatTokenCount } from '@/utils/trace-utils';
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

function EmptyCell() {
  return (
    <Typography variant="body2" sx={{ color: 'text.disabled' }}>
      —
    </Typography>
  );
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
      if (!hasUsage(row)) return <EmptyCell />;
      const value = params.value as number | null;
      if (value === null || value === undefined) return <EmptyCell />;
      return (
        <Typography
          variant="body2"
          sx={{ fontVariantNumeric: 'tabular-nums' }}
          title={tooltip(row)}
        >
          {format(value)}
        </Typography>
      );
    },
  };
}

function tokenSplit(row: TestRunDetail): string | undefined {
  const usage = row.usage;
  if (!usage) return undefined;
  return `${formatTokenCount(usage.total_input_tokens)} input · ${formatTokenCount(
    usage.total_output_tokens
  )} output`;
}

function costSplit(row: TestRunDetail): string | undefined {
  const usage = row.usage;
  if (!usage) return undefined;
  return `${formatCost(usage.total_input_cost_usd)} input · ${formatCost(
    usage.total_output_cost_usd
  )} output`;
}

/** `provider/model`, plus `+N` when the run used more than one. */
function ModelCell({ row }: { row: TestRunDetail }) {
  const usage = row.usage;
  const models = usage?.models ?? [];
  if (models.length === 0) return <EmptyCell />;

  const provider = usage?.providers?.[0];
  const first = provider ? `${provider}/${models[0]}` : models[0];
  const label = models.length > 1 ? `${first} +${models.length - 1}` : first;
  const full = models.join(', ');

  return (
    <Tooltip title={models.length > 1 ? full : ''}>
      <Typography
        variant="body2"
        sx={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </Typography>
    </Tooltip>
  );
}

export function usageColumns(): GridColDef[] {
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
    numericColumn('total_cost_usd', 'Cost', formatCost, costSplit),
    numericColumn('total_input_cost_usd', 'Input cost', formatCost, costSplit),
    numericColumn(
      'total_output_cost_usd',
      'Output cost',
      formatCost,
      costSplit
    ),
    {
      field: 'usage.models',
      headerName: 'Model',
      flex: 1.6,
      minWidth: 120,
      filterable: false,
      // Sorted by the run's alphabetically first model, which is the one shown here.
      valueGetter: (_, row: TestRunDetail) => row.usage?.models?.[0] ?? null,
      renderCell: params => <ModelCell row={params.row as TestRunDetail} />,
    },
  ];
}
