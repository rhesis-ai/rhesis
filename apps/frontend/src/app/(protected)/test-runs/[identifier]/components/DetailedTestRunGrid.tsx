'use client';

import { useCallback, useMemo, useState } from 'react';
import {
  Box,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
} from '@mui/material';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import {
  DataGrid,
  GridColDef,
  GridPaginationModel,
  GridRenderCellParams,
  GridColumnGroupingModel,
  GridRowParams,
} from '@mui/x-data-grid';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import CloseIcon from '@mui/icons-material/Close';
import { useRouter } from 'next/navigation';
import styles from '@/styles/DetailedTestRunGrid.module.css';
import { useTestRunData } from '../hooks/useTestRunData';

interface DetailedTestRunGridProps {
  testRunId: string;
  sessionToken: string;
  open: boolean;
  onClose: () => void;
}

export default function DetailedTestRunGrid({
  testRunId,
  sessionToken,
  open,
  onClose,
}: DetailedTestRunGridProps) {
  const router = useRouter();
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });

  const { testResults, prompts, behaviors, loading, totalCount, error } =
    useTestRunData({
      testRunId,
      sessionToken,
      paginationModel,
      enabled: open, // Only fetch data when modal is open
    });

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const handleRowClick = useCallback(
    (params: GridRowParams<TestResultDetail>) => {
      if (params.row.test_id) {
        router.push(`/tests/${params.row.test_id}`);
      }
    },
    [router]
  );

  const renderMetricCell = useCallback((params: GridRenderCellParams) => {
    const value = params.value;
    if (value === 'N/A') return value;

    const { status, score, threshold, reference_score, reason } = value as {
      status: string;
      score: number | string;
      threshold?: number;
      reference_score?: string;
      reason: string;
    };
    const isPassed = status === 'Passed';

    // Determine if this is a binary/categorical metric (has reference_score) or numeric (has threshold)
    const isBinaryOrCategorical = reference_score !== undefined;

    return (
      <Box
        className={`${styles.metricCell} ${isPassed ? styles.metricCellPassed : styles.metricCellFailed}`}
      >
        <Tooltip
          title={reason ?? 'No reason provided'}
          enterDelay={1000}
          leaveDelay={0}
          enterNextDelay={1000}
        >
          <Box
            component="span"
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {isPassed ? (
              <CheckCircleOutlineIcon style={{ fontSize: 16 }} />
            ) : (
              <CancelOutlinedIcon style={{ fontSize: 16 }} />
            )}
          </Box>
        </Tooltip>
        <span className={styles.metricScore}>
          {
            isBinaryOrCategorical
              ? `${score} (${reference_score})` // For binary/categorical: show "actual (expected)"
              : `${typeof score === 'number' ? score.toFixed(1) : score}/${threshold?.toFixed(1) || 'N/A'}` // For numeric: show "score/threshold"
          }
        </span>
      </Box>
    );
  }, []);

  const baseColumns: GridColDef<TestResultDetail>[] = useMemo(
    () => [
      {
        field: 'prompt_name',
        headerName: 'Test',
        flex: 1,
        minWidth: 250,
        headerClassName: 'bold-header',
        renderCell: params => {
          const content =
            params.row.prompt_id && prompts[params.row.prompt_id]
              ? prompts[params.row.prompt_id].content
              : 'N/A';
          return (
            <Tooltip
              title={content}
              enterDelay={1500}
              leaveDelay={0}
              enterNextDelay={1500}
            >
              <Box className={styles.tooltipContent}>
                {content.substring(0, 60) + '...'}
              </Box>
            </Tooltip>
          );
        },
      },
      {
        field: 'response',
        headerName: 'Response',
        flex: 1,
        minWidth: 250,
        headerClassName: 'bold-header',
        renderCell: params => {
          const content = params.row.test_output?.output ?? 'N/A';
          return (
            <Tooltip
              title={content}
              enterDelay={1500}
              leaveDelay={0}
              enterNextDelay={1500}
            >
              <Box className={styles.tooltipContent}>
                {content === 'N/A' ? content : content.substring(0, 60) + '...'}
              </Box>
            </Tooltip>
          );
        },
      },
    ],
    [prompts]
  );

  // Create metric columns grouped by behavior
  const { metricColumns, columnGroupingModel } = useMemo(() => {
    const metricCols: GridColDef<TestResultDetail>[] = [];
    const grouping: GridColumnGroupingModel = [];

    behaviors.forEach(behavior => {
      if (behavior.metrics.length === 0) return;

      // Create columns for each metric in this behavior
      const behaviorMetricColumns = behavior.metrics.map(metric => ({
        field: `${behavior.id}_${metric.id}`,
        headerName: metric.name
          .split('_')
          .map(word => word.charAt(0).toUpperCase() + word.slice(1))
          .join(' '),
        width: 140,
        renderCell: renderMetricCell,
        valueGetter: (_value: any, row: TestResultDetail) => {
          const testMetrics = row.test_metrics?.metrics;
          if (!testMetrics) return 'N/A';

          const metricResult = testMetrics[metric.name];
          if (!metricResult) return 'N/A';

          return {
            status: metricResult.is_successful ? 'Passed' : 'Failed',
            score: metricResult.score,
            threshold: metricResult.threshold,
            reference_score: metricResult.reference_score,
            reason: metricResult.reason,
          };
        },
      }));

      metricCols.push(...behaviorMetricColumns);

      // Add column group for this behavior
      grouping.push({
        groupId: behavior.id,
        headerName: behavior.name,
        description: behavior.description || undefined,
        children: behaviorMetricColumns.map(col => ({ field: col.field })),
      });
    });

    return { metricColumns: metricCols, columnGroupingModel: grouping };
  }, [behaviors, renderMetricCell]);

  const columns = useMemo(
    () => [...baseColumns, ...metricColumns],
    [baseColumns, metricColumns]
  );

  if (error) {
    return (
      <Dialog open={open} onClose={onClose}>
        <DialogContent>
          <Box sx={{ p: 2, textAlign: 'center', color: 'error.main' }}>
            Error: {error}
          </Box>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={false}
      fullWidth
      PaperProps={{
        sx: {
          width: '95vw',
          height: '90vh',
          maxWidth: 'none',
          maxHeight: 'none',
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pb: 1,
        }}
      >
        Detailed Test Run Results
        <IconButton
          aria-label="close"
          onClick={onClose}
          sx={{
            color: theme => theme.palette.grey[500],
          }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers sx={{ p: 0, overflow: 'hidden' }}>
        <DataGrid
          rows={testResults}
          columns={columns}
          loading={loading}
          pageSizeOptions={[10, 25, 50]}
          paginationModel={paginationModel}
          onPaginationModelChange={handlePaginationModelChange}
          getRowId={row => row.id}
          onRowClick={handleRowClick}
          density="compact"
          disableRowSelectionOnClick
          disableMultipleRowSelection
          paginationMode="server"
          rowCount={totalCount}
          columnGroupingModel={columnGroupingModel}
          sx={{
            border: 'none',
            '& .MuiDataGrid-row': {
              cursor: 'pointer',
              '&:hover': {
                backgroundColor: 'action.hover',
              },
            },
            '& .MuiDataGrid-columnHeaders': {
              backgroundColor: 'background.paper',
              borderBottom: '2px solid',
              borderBottomColor: 'divider',
            },
            '& .bold-header': {
              fontWeight: 'bold',
            },
            '& .MuiDataGrid-columnHeaderTitle': {
              fontWeight: 'bold',
            },
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
