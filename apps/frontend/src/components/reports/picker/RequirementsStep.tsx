'use client';

import * as React from 'react';
import { Box, Button, Stack, Typography } from '@mui/material';
import type {
  GridColDef,
  GridRenderCellParams,
  GridRowSelectionModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { PAGE_LIMIT } from '@/components/reports/picker/useReportPickerData';

export interface RequirementOptionRow {
  id: string;
  name: string;
  parent_id?: string | null;
}

interface TreeRow extends RequirementOptionRow {
  level: number;
  tested: boolean;
}

/** Parents first, each followed by its children. */
function asTree(
  requirements: RequirementOptionRow[],
  tested: ReadonlySet<string>
): TreeRow[] {
  const ids = new Set(requirements.map(r => r.id));
  const children = new Map<string, RequirementOptionRow[]>();
  const tops: RequirementOptionRow[] = [];
  for (const r of requirements) {
    if (r.parent_id && ids.has(r.parent_id)) {
      children.set(r.parent_id, [...(children.get(r.parent_id) ?? []), r]);
    } else {
      tops.push(r);
    }
  }
  const byName = (a: RequirementOptionRow, b: RequirementOptionRow) =>
    a.name.localeCompare(b.name);
  const row = (r: RequirementOptionRow, level: number): TreeRow => ({
    ...r,
    level,
    tested: tested.has(r.id),
  });
  return tops
    .sort(byName)
    .flatMap(top => [
      row(top, 0),
      ...(children.get(top.id) ?? []).sort(byName).map(c => row(c, 1)),
    ]);
}

const COLUMNS: GridColDef[] = [
  {
    field: 'name',
    headerName: 'Requirement',
    flex: 2,
    sortable: false,
    renderCell: (params: GridRenderCellParams<TreeRow>) => (
      <Box
        component="span"
        sx={{
          pl: params.row.level * 3,
          fontWeight: params.row.level === 0 ? 500 : undefined,
        }}
      >
        {params.row.name}
      </Box>
    ),
  },
  {
    field: 'tested',
    headerName: 'In the picked runs',
    flex: 1,
    sortable: false,
    renderCell: (params: GridRenderCellParams<TreeRow>) => (
      <Typography
        variant="body2"
        color={params.row.tested ? 'text.primary' : 'text.secondary'}
      >
        {params.row.tested ? 'Tested' : 'Not tested'}
      </Typography>
    ),
  },
];

interface RequirementsStepProps {
  requirements: RequirementOptionRow[];
  loading: boolean;
  /** Requirements with results in the picked runs. */
  tested: ReadonlySet<string>;
  selected: string[];
  onChange: (ids: string[]) => void;
  /** There are more requirements than were loaded. */
  truncated?: boolean;
}

export default function RequirementsStep({
  requirements,
  loading,
  tested,
  selected,
  onChange,
  truncated = false,
}: RequirementsStepProps) {
  const rows = React.useMemo(
    () => asTree(requirements, tested),
    [requirements, tested]
  );

  return (
    <Stack spacing={2}>
      <Stack
        direction="row"
        spacing={2}
        alignItems="center"
        justifyContent="space-between"
        flexWrap="wrap"
      >
        <Typography variant="body2" color="text.secondary">
          The picked runs tested {tested.size} requirement
          {tested.size === 1 ? '' : 's'}; they are picked for you. Add
          requirements without results to show their gap in the report.
        </Typography>
        <Button
          size="small"
          onClick={() => onChange([...tested])}
          disabled={loading}
        >
          Pick only the tested ones
        </Button>
      </Stack>
      {!loading && rows.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          This project has no requirements yet. The report still counts every
          result.
        </Typography>
      ) : (
        <Box sx={{ width: '100%' }}>
          <BaseDataGrid
            rows={rows}
            columns={COLUMNS}
            loading={loading}
            getRowId={row => String(row.id)}
            checkboxSelection
            keepNonExistentRowsSelected
            disableColumnResize
            rowSelectionModel={selected}
            onRowSelectionModelChange={(model: GridRowSelectionModel) =>
              onChange(model.map(String))
            }
            disablePaperWrapper
            pageSizeOptions={[10, 25, 50]}
            initialState={{
              pagination: { paginationModel: { page: 0, pageSize: 25 } },
            }}
          />
        </Box>
      )}
      {truncated && (
        <Typography variant="caption" color="text.secondary">
          Showing the first {PAGE_LIMIT} requirements. Ones you picked before
          stay in the report.
        </Typography>
      )}
    </Stack>
  );
}
