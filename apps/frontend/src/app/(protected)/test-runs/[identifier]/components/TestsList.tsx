'use client';

import React, { useMemo, useEffect, useRef, useState } from 'react';
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  Typography,
  Paper,
  Skeleton,
  useTheme,
  TablePagination,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import ChatIcon from '@mui/icons-material/Chat';
import TaskIcon from '@mui/icons-material/Task';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

interface TestsListProps {
  tests: TestResultDetail[];
  selectedTestId: string | null;
  onTestSelect: (testId: string) => void;
  loading?: boolean;
  prompts: Record<string, { content: string; name?: string }>;
}

interface TestListItemProps {
  test: TestResultDetail;
  isSelected: boolean;
  onClick: () => void;
  promptContent: string;
  isPassed: boolean;
  passedMetrics: number;
  totalMetrics: number;
}

function TestListItemSkeleton() {
  return (
    <ListItem disablePadding>
      <Paper
        sx={{
          width: '100%',
          p: 2,
          mb: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
          <Skeleton variant="circular" width={24} height={24} />
          <Box sx={{ flex: 1 }}>
            <Skeleton variant="text" width="80%" height={20} />
            <Skeleton variant="text" width="60%" height={16} sx={{ mt: 1 }} />
            <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
              <Skeleton
                variant="rectangular"
                width={60}
                height={20}
                sx={{ borderRadius: theme => theme.shape.borderRadius }}
              />
              <Skeleton
                variant="rectangular"
                width={60}
                height={20}
                sx={{ borderRadius: theme => theme.shape.borderRadius }}
              />
            </Box>
          </Box>
        </Box>
      </Paper>
    </ListItem>
  );
}

function TestListItem({
  test,
  isSelected,
  onClick,
  promptContent,
  isPassed,
  passedMetrics,
  totalMetrics,
}: TestListItemProps) {
  const theme = useTheme();

  // Truncate prompt content for display
  const truncatedPrompt =
    promptContent.length > 100
      ? `${promptContent.substring(0, 100)}...`
      : promptContent;

  return (
    <ListItem disablePadding sx={{ mb: 1 }}>
      <Paper
        elevation={isSelected ? 3 : 1}
        sx={{
          width: '100%',
          transition: 'all 0.2s',
          border: isSelected
            ? `2px solid ${theme.palette.primary.main}`
            : '2px solid transparent',
          '&:hover': {
            elevation: 2,
            transform: 'translateX(4px)',
          },
        }}
      >
        <ListItemButton
          selected={isSelected}
          onClick={onClick}
          sx={{
            p: 2,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            gap: 1.5,
          }}
        >
          {/* Status Icon and Prompt */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 2,
              width: '100%',
            }}
          >
            <Box
              sx={{
                flexShrink: 0,
                color: isPassed ? 'success.main' : 'error.main',
                display: 'flex',
                alignItems: 'center',
                mt: 0.5,
              }}
            >
              {isPassed ? (
                <CheckCircleOutlineIcon fontSize="small" />
              ) : (
                <CancelOutlinedIcon fontSize="small" />
              )}
            </Box>

            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: isSelected ? 600 : 400,
                  color: 'text.primary',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  lineHeight: 1.4,
                }}
              >
                {truncatedPrompt}
              </Typography>
            </Box>
          </Box>

          {/* Metrics Summary and Counts */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              width: '100%',
              flexWrap: 'wrap',
            }}
          >
            <Typography
              variant="caption"
              sx={{
                color: isPassed ? 'success.main' : 'error.main',
                fontWeight: 500,
              }}
            >
              {passedMetrics}/{totalMetrics} metrics
            </Typography>

            {/* Comments Count */}
            {test.counts && test.counts.comments > 0 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <ChatIcon sx={{ fontSize: 12, color: 'text.secondary' }} />
                <Typography variant="caption" color="text.secondary">
                  {test.counts.comments}
                </Typography>
              </Box>
            )}

            {/* Tasks Count */}
            {test.counts && test.counts.tasks > 0 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <TaskIcon sx={{ fontSize: 12, color: 'text.secondary' }} />
                <Typography variant="caption" color="text.secondary">
                  {test.counts.tasks}
                </Typography>
              </Box>
            )}
          </Box>
        </ListItemButton>
      </Paper>
    </ListItem>
  );
}

export default function TestsList({
  tests,
  selectedTestId,
  onTestSelect,
  loading = false,
  prompts,
}: TestsListProps) {
  const theme = useTheme();
  const listContainerRef = useRef<HTMLDivElement>(null);
  const selectedItemRef = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
    // Scroll to top of list when page changes
    if (listContainerRef.current) {
      listContainerRef.current.scrollTop = 0;
    }
  };

  const handleChangeRowsPerPage = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  // Process tests to determine pass/fail status
  const processedTests = useMemo(() => {
    return tests.map(test => {
      const metrics = test.test_metrics?.metrics || {};
      const metricValues = Object.values(metrics);
      const passedMetrics = metricValues.filter(m => m.is_successful).length;
      const totalMetrics = metricValues.length;
      const isPassed = totalMetrics > 0 && passedMetrics === totalMetrics;

      const promptContent =
        test.prompt_id && prompts[test.prompt_id]
          ? prompts[test.prompt_id].content
          : 'No prompt available';

      return {
        test,
        isPassed,
        passedMetrics,
        totalMetrics,
        promptContent,
      };
    });
  }, [tests, prompts]);

  // Paginated tests
  const paginatedTests = useMemo(() => {
    return processedTests.slice(
      page * rowsPerPage,
      page * rowsPerPage + rowsPerPage
    );
  }, [processedTests, page, rowsPerPage]);

  // Handle keyboard navigation (within current page)
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (paginatedTests.length === 0) return;

      const currentIndex = paginatedTests.findIndex(
        item => item.test.id === selectedTestId
      );

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        const nextIndex =
          currentIndex < paginatedTests.length - 1 ? currentIndex + 1 : 0;
        onTestSelect(paginatedTests[nextIndex].test.id);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        const prevIndex =
          currentIndex > 0 ? currentIndex - 1 : paginatedTests.length - 1;
        onTestSelect(paginatedTests[prevIndex].test.id);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [paginatedTests, selectedTestId, onTestSelect]);

  // Scroll selected item into view
  useEffect(() => {
    if (selectedItemRef.current && listContainerRef.current) {
      selectedItemRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      });
    }
  }, [selectedTestId]);

  if (loading) {
    return (
      <>
        <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            pr: 1,
          }}
        >
          <List>
            {Array.from({ length: 5 }).map((_, index) => (
              <TestListItemSkeleton key={index} />
            ))}
          </List>
        </Box>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50, 100]}
          component="div"
          count={tests.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
          sx={{
            borderTop: 1,
            borderColor: 'divider',
            backgroundColor: theme.palette.background.paper,
            flexShrink: 0,
          }}
        />
      </>
    );
  }

  if (tests.length === 0) {
    return (
      <>
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            p: 4,
          }}
        >
          <Typography variant="body2" color="text.secondary" textAlign="center">
            No tests found matching your filters
          </Typography>
        </Box>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50, 100]}
          component="div"
          count={tests.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
          sx={{
            borderTop: 1,
            borderColor: 'divider',
            backgroundColor: theme.palette.background.paper,
            flexShrink: 0,
          }}
        />
      </>
    );
  }

  return (
    <>
      <Box
        ref={listContainerRef}
        sx={{
          flex: 1,
          overflow: 'auto',
          pr: 1,
          // Custom scrollbar styling
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-track': {
            background: theme.palette.background.default,
            borderRadius: '4px',
          },
          '&::-webkit-scrollbar-thumb': {
            background: theme.palette.divider,
            borderRadius: '4px',
            '&:hover': {
              background: theme.palette.action.hover,
            },
          },
        }}
      >
        <List sx={{ py: 0 }}>
          {paginatedTests.map(
            ({ test, isPassed, passedMetrics, totalMetrics, promptContent }) => (
              <Box
                key={test.id}
                ref={selectedTestId === test.id ? selectedItemRef : null}
              >
                <TestListItem
                  test={test}
                  isSelected={selectedTestId === test.id}
                  onClick={() => onTestSelect(test.id)}
                  promptContent={promptContent}
                  isPassed={isPassed}
                  passedMetrics={passedMetrics}
                  totalMetrics={totalMetrics}
                />
              </Box>
            )
          )}
        </List>
      </Box>

      {/* Pagination */}
      <TablePagination
        rowsPerPageOptions={[10, 25, 50, 100]}
        component="div"
        count={tests.length}
        rowsPerPage={rowsPerPage}
        page={page}
        onPageChange={handleChangePage}
        onRowsPerPageChange={handleChangeRowsPerPage}
        sx={{
          borderTop: 1,
          borderColor: 'divider',
          backgroundColor: theme.palette.background.paper,
          flexShrink: 0,
        }}
      />
    </>
  );
}
