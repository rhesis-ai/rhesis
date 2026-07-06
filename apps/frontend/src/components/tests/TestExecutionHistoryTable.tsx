'use client';

import React from 'react';
import {
  Box,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  useTheme,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import Link from 'next/link';
import { formatDate } from '@/utils/date';
import StatusChip from '@/components/common/StatusChip';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';
import { TestExecutionHistoryRow } from './test-execution-history';

interface TestExecutionHistoryTableProps {
  rows: TestExecutionHistoryRow[];
  highlightTestRunId?: string;
}

export default function TestExecutionHistoryTable({
  rows,
  highlightTestRunId,
}: TestExecutionHistoryTableProps) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        bgcolor: 'background.paper',
        borderRadius: BORDER_RADIUS.md,
        border: 1,
        borderColor: 'divider',
        boxShadow: ELEVATION.xs,
        overflow: 'hidden',
      }}
    >
      <TableContainer>
        <Table
          sx={{
            '& .MuiTableCell-root': {
              borderBottom: 1,
              borderColor: 'divider',
              fontSize: 14,
              lineHeight: '22px',
              py: '13px',
              px: '12px',
              bgcolor: 'background.paper',
            },
            '& .MuiTableBody-root .MuiTableRow-root:last-child .MuiTableCell-root':
              {
                borderBottom: 'none',
              },
            '& .MuiTableRow-root:hover .MuiTableCell-root': {
              bgcolor: 'action.hover',
            },
          }}
        >
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 700, color: 'text.primary' }}>
                Status
              </TableCell>
              <TableCell sx={{ fontWeight: 700, color: 'text.primary' }}>
                Test Run
              </TableCell>
              <TableCell sx={{ fontWeight: 700, color: 'text.primary' }}>
                Metrics
              </TableCell>
              <TableCell sx={{ fontWeight: 700, color: 'text.primary' }}>
                Executed At
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map(item => (
              <TableRow key={item.id}>
                <TableCell>
                  <StatusChip
                    passed={item.passed}
                    label={item.passed ? 'Pass' : 'Fail'}
                    size="small"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {item.testRunId !== 'unknown' ? (
                      <Link
                        href={`/test-runs/${item.testRunId}?selectedresult=${item.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ textDecoration: 'none' }}
                      >
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 0.5,
                            '&:hover .test-run-name': {
                              color: theme.palette.primary.main,
                              textDecoration: 'underline',
                            },
                          }}
                        >
                          <Typography
                            className="test-run-name"
                            sx={{
                              fontSize: 14,
                              lineHeight: '22px',
                              transition: 'color 0.2s',
                              color: 'text.primary',
                              fontWeight:
                                item.testRunId === highlightTestRunId
                                  ? 600
                                  : 400,
                            }}
                          >
                            {item.testRunName}
                          </Typography>
                          <OpenInNewIcon
                            sx={{ fontSize: 14, color: 'text.disabled' }}
                          />
                        </Box>
                      </Link>
                    ) : (
                      <Typography
                        sx={{
                          fontSize: 14,
                          lineHeight: '22px',
                          color: 'text.primary',
                        }}
                      >
                        {item.testRunName}
                      </Typography>
                    )}
                    {highlightTestRunId &&
                      item.testRunId === highlightTestRunId && (
                        <Chip
                          label="Current"
                          size="small"
                          variant="outlined"
                          sx={{
                            borderColor: 'divider',
                            color: 'text.primary',
                            fontSize: 12,
                          }}
                        />
                      )}
                  </Box>
                </TableCell>
                <TableCell sx={{ color: 'text.primary' }}>
                  {item.passedMetrics}/{item.totalMetrics} passed
                </TableCell>
                <TableCell sx={{ color: 'text.secondary' }}>
                  {formatDate(item.executedAt)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
