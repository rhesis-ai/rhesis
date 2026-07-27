'use client';

import React from 'react';
import {
  Box,
  IconButton,
  MenuItem,
  Select,
  TableCell,
  Typography,
} from '@mui/material';
import type { Theme } from '@mui/material/styles';
import ArrowBackIosNewIcon from '@mui/icons-material/ArrowBackIosNew';
import ArrowForwardIosIcon from '@mui/icons-material/ArrowForwardIos';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { overviewTableInnerSx } from '@/components/common/SectionCard';
import { ROW_ACTIONS_CLASS } from '@/components/common/createRowActionsColumn';

/** Figma node 1640:23151 — overview table header cell inside section cards. */
export const sectionOverviewHeaderCellSx = {
  fontWeight: 700,
  fontSize: 14,
  lineHeight: '22px',
  color: 'greyscale.body',
  height: 48,
  p: 0,
  bgcolor: 'background.paper',
  borderBottom: 'none',
  verticalAlign: 'middle',
} as const;

/** Figma node 1640:23151 — overview table body cell inside section cards. */
export const sectionOverviewBodyCellSx = {
  fontSize: 14,
  lineHeight: '22px',
  color: 'greyscale.body',
  py: '12px',
  px: '12px',
  borderTop: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
  borderBottom: 'none',
  height: 48,
  bgcolor: 'background.paper',
  verticalAlign: 'middle',
} as const;

/** Table styles shared by section-card overview tables (Roles, Team, …). */
export const sectionOverviewTableSx = {
  ...overviewTableInnerSx,
  [`& .${ROW_ACTIONS_CLASS}`]: {
    opacity: 0,
    pointerEvents: 'none',
    transition: 'opacity 0.15s ease',
  },
  [`& .MuiTableRow-root:hover .${ROW_ACTIONS_CLASS}, & .MuiTableRow-root:focus-within .${ROW_ACTIONS_CLASS}`]:
    {
      opacity: 1,
      pointerEvents: 'auto',
    },
} as const;

export function SectionOverviewHeaderCell({
  children,
  showDivider = false,
  width,
}: {
  children?: React.ReactNode;
  showDivider?: boolean;
  width?: number | string;
}) {
  return (
    <TableCell sx={{ ...sectionOverviewHeaderCellSx, width }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          height: 48,
          pl: 0,
          pr: '12px',
        }}
      >
        {showDivider && (
          <Box
            sx={{
              width: '1px',
              height: 23,
              bgcolor: 'greyscale.border',
              mx: '12px',
              flexShrink: 0,
            }}
          />
        )}
        {children && (
          <Typography
            component="span"
            sx={{
              fontWeight: 700,
              fontSize: 14,
              lineHeight: '22px',
              color: 'greyscale.body',
            }}
          >
            {children}
          </Typography>
        )}
      </Box>
    </TableCell>
  );
}

export const sectionOverviewRowActionIconButtonSx = {
  p: 0.5,
  color: 'text.secondary',
} as const;

interface SectionOverviewPaginationProps {
  page: number;
  pageSize: number;
  totalRows: number;
  pageSizeOptions?: number[];
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

function paginationNavBtnSx(active: boolean): Record<string, unknown> {
  return {
    border: '2px solid',
    borderColor: active ? 'primary.main' : 'greyscale.border',
    borderRadius: BORDER_RADIUS.sm,
    p: '9px',
    width: 38,
    height: 38,
    flexShrink: 0,
    color: active ? 'primary.main' : 'greyscale.border',
    '&.Mui-disabled': {
      borderColor: 'greyscale.border',
      color: 'greyscale.border',
      opacity: 1,
    },
    '&:hover': {
      bgcolor: active ? 'rgba(0, 128, 175, 0.06)' : 'transparent',
    },
    '& .MuiSvgIcon-root': { fontSize: 16 },
  };
}

/** Pagination footer matching BaseDataGrid / Figma section-card tables. */
export function SectionOverviewPagination({
  page,
  pageSize,
  totalRows,
  pageSizeOptions = [10, 25, 50, 100],
  onPageChange,
  onPageSizeChange,
}: SectionOverviewPaginationProps) {
  const from = totalRows === 0 ? 0 : page * pageSize + 1;
  const to = Math.min((page + 1) * pageSize, totalRows);
  const isFirst = page === 0;
  const isLast = totalRows === 0 || to >= totalRows;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        px: '30px',
        py: '16px',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
        <Typography
          sx={{
            fontSize: 12,
            fontWeight: 600,
            color: 'greyscale.body',
            whiteSpace: 'nowrap',
          }}
        >
          Rows per page:
        </Typography>
        <Select
          value={pageSize}
          onChange={e => onPageSizeChange(Number(e.target.value))}
          variant="standard"
          disableUnderline
          sx={{
            fontSize: 14,
            fontWeight: 700,
            color: 'greyscale.body',
            '& .MuiSelect-icon': { color: 'greyscale.body' },
          }}
        >
          {pageSizeOptions.map(opt => (
            <MenuItem key={opt} value={opt} sx={{ fontSize: 14 }}>
              {opt}
            </MenuItem>
          ))}
        </Select>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: '30px' }}>
        <IconButton
          onClick={() => onPageChange(page - 1)}
          disabled={isFirst}
          aria-label="Previous page"
          sx={paginationNavBtnSx(!isFirst)}
        >
          <ArrowBackIosNewIcon />
        </IconButton>

        <Typography
          sx={{
            fontSize: 12,
            fontWeight: 600,
            color: 'greyscale.body',
            whiteSpace: 'nowrap',
          }}
        >
          {from}–{to} of {totalRows}
        </Typography>

        <IconButton
          onClick={() => onPageChange(page + 1)}
          disabled={isLast}
          aria-label="Next page"
          sx={paginationNavBtnSx(!isLast)}
        >
          <ArrowForwardIosIcon />
        </IconButton>
      </Box>
    </Box>
  );
}
