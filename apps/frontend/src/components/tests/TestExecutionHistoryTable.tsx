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
import { TestExecutionHistoryRow } from './test-execution-history';

interface TestExecutionHistoryTableProps {
  rows: TestExecutionHistoryRow[];
  testId?: string;
  highlightTestRunId?: string;
}

export default function TestExecutionHistoryTable({
  rows,
  testId,
  highlightTestRunId,
}: TestExecutionHistoryTableProps) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        bgcolor: 'background.paper',
        borderRadius: '12px',
        border: '1px solid #cdd2da',
        boxShadow: '0px 2px 4px rgba(84,90,101,0.25)',
        overflow: 'hidden',
      }}
    >
      <TableContainer>
        <Table
          sx={{
            '& .MuiTableCell-root': {
              borderBottom: '1px solid #cdd2da',
              fontSize: 14,
              lineHeight: '22px',
              py: '13px',
              px: '12px',
              backgroundColor: '#ffffff',
            },
            '& .MuiTableBody-root .MuiTableRow-root:last-child .MuiTableCell-root':
              {
                borderBottom: 'none',
              },
            '& .MuiTableRow-root:hover .MuiTableCell-root': {
              backgroundColor: '#f9fafb',
            },
          }}
        >
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 700, color: '#2a2e36' }}>
                Status
              </TableCell>
              <TableCell sx={{ fontWeight: 700, color: '#2a2e36' }}>
                Test Run
              </TableCell>
              <TableCell sx={{ fontWeight: 700, color: '#2a2e36' }}>
                Metrics
              </TableCell>
              <TableCell sx={{ fontWeight: 700, color: '#2a2e36' }}>
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
                    sx={{
                      borderColor: item.passed ? '#38ad87' : '#de3355',
                      color: item.passed ? '#38ad87' : '#de3355',
                      '& .MuiChip-icon': { color: 'inherit' },
                    }}
                  />
                </TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {item.testRunId !== 'unknown' ? (
                      <Link
                        href={`/test-runs/${item.testRunId}${testId ? `?selectedresult=${testId}` : ''}`}
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
                              color: '#2a2e36',
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
                          color: '#2a2e36',
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
                            borderColor: '#cdd2da',
                            color: '#2a2e36',
                            fontSize: 12,
                          }}
                        />
                      )}
                  </Box>
                </TableCell>
                <TableCell sx={{ color: '#2a2e36' }}>
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
