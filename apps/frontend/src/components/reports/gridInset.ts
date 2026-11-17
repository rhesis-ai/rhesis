import type { SxProps, Theme } from '@mui/material/styles';
import type { GridColDef } from '@mui/x-data-grid';

const FIRST = 'report-grid-first';
const LAST = 'report-grid-last';

/**
 * The card's 30px inset on a report grid's first and last columns.
 *
 * BaseDataGrid's own inset targets `.MuiDataGrid-cell:first-child`, but DataGrid v7
 * starts each row with an offset spacer div, so that rule misses the first real
 * cell. Marking the columns with classes doesn't depend on the row's markup.
 */
export function withEdgeInset(columns: GridColDef[]): GridColDef[] {
  return columns.map((column, index) => {
    const edge =
      index === 0 ? FIRST : index === columns.length - 1 ? LAST : undefined;
    return edge
      ? { ...column, headerClassName: edge, cellClassName: edge }
      : column;
  });
}

export const gridEdgeInsetSx: SxProps<Theme> = {
  [`& .${FIRST}`]: { paddingLeft: theme => theme.spacing(3.75) },
  [`& .${LAST}`]: { paddingRight: theme => theme.spacing(3.75) },
};
