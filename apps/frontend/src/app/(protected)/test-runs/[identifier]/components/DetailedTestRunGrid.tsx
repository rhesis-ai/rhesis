'use client';

import { useEffect, useState } from 'react';
import { Box, Tooltip, Dialog, DialogTitle, DialogContent, IconButton } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultDetail, MetricResult } from '@/utils/api-client/interfaces/test-results';
import { Prompt } from '@/utils/api-client/interfaces/prompt';
import { Behavior } from '@/utils/api-client/interfaces/behavior';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import { DataGrid, GridColDef, GridPaginationModel, GridRenderCellParams, GridColumnGroupingModel, GridRowParams } from '@mui/x-data-grid';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import CloseIcon from '@mui/icons-material/Close';
import { useRouter } from 'next/navigation';
import { UUID } from 'crypto';
import styles from '@/styles/DetailedTestRunGrid.module.css';

interface DetailedTestRunGridProps {
  testRunId: string;
  sessionToken: string;
  open: boolean;
  onClose: () => void;
}

interface BehaviorWithMetrics extends Behavior {
  metrics: MetricDetail[];
}

export default function DetailedTestRunGrid({ testRunId, sessionToken, open, onClose }: DetailedTestRunGridProps) {
  const router = useRouter();
  const [testResults, setTestResults] = useState<TestResultDetail[]>([]);
  const [prompts, setPrompts] = useState<Record<string, Prompt>>({});
  const [loading, setLoading] = useState(true);
  const [behaviors, setBehaviors] = useState<BehaviorWithMetrics[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });

  useEffect(() => {
    if (!open) return;

    const fetchTestResults = async () => {
      try {
        setLoading(true);
        const apiFactory = new ApiClientFactory(sessionToken);
        const testResultsClient = apiFactory.getTestResultsClient();
        const promptsClient = apiFactory.getPromptsClient();
        const behaviorClient = apiFactory.getBehaviorClient();
        
        // Calculate skip based on pagination model
        const skip = paginationModel.page * paginationModel.pageSize;
        
        // Fetch test results with pagination parameters
        const response = await testResultsClient.getTestResults({
          filter: `test_run_id eq '${testRunId}'`,
          skip: skip,
          limit: paginationModel.pageSize,
          sortBy: 'created_at',
          sortOrder: 'desc'
        });
        
        const results = response.data;
        setTotalCount(response.pagination.totalCount);
        
        // Get unique prompt IDs
        const promptIds = [...new Set(results.filter((r: TestResultDetail) => r.prompt_id).map((r: TestResultDetail) => r.prompt_id!))];
        
        // Fetch all prompts in parallel
        const promptsData = await Promise.all(
          promptIds.map((id: string) => promptsClient.getPrompt(id))
        );
        
        // Create a map of prompt ID to prompt data
        const promptsMap = promptsData.reduce((acc, prompt) => {
          acc[prompt.id] = prompt;
          return acc;
        }, {} as Record<string, Prompt>);

        // Fetch all behaviors
        const behaviorsData = await behaviorClient.getBehaviors({
          sort_by: 'name',
          sort_order: 'asc'
        });

        // Fetch metrics for each behavior
        const behaviorsWithMetrics = await Promise.all(
          behaviorsData.map(async (behavior) => {
            try {
              // Type assertion needed due to type definition mismatch
              const behaviorMetrics = await (behaviorClient as any).getBehaviorMetrics(behavior.id as UUID);
              return {
                ...behavior,
                metrics: behaviorMetrics
              };
            } catch (error) {
              console.error(`Error fetching metrics for behavior ${behavior.id}:`, error);
              return {
                ...behavior,
                metrics: []
              };
            }
          })
        );

        // Filter out behaviors that have no metrics
        const behaviorsWithMetricsFiltered = behaviorsWithMetrics.filter(behavior => behavior.metrics.length > 0);
        
        setBehaviors(behaviorsWithMetricsFiltered);
        setPrompts(promptsMap);
        setTestResults(results);
      } catch (error) {
        console.error('Error fetching test results:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchTestResults();
  }, [testRunId, sessionToken, paginationModel, open]);

  const handlePaginationModelChange = (newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  };

  const handleRowClick = (params: GridRowParams<TestResultDetail>) => {
    if (params.row.test_id) {
      router.push(`/tests/${params.row.test_id}`);
    }
  };

  const renderMetricCell = (params: GridRenderCellParams) => {
    const value = params.value;
    if (value === 'N/A') return value;
    
    const { status, score, threshold, reason } = value as { 
      status: string; 
      score: number; 
      threshold: number; 
      reason: string;
    };
    const isPassed = status === 'Passed';
    
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
          <Box component="span">
            {isPassed ? (
              <CheckCircleOutlineIcon style={{ fontSize: 16 }} />
            ) : (
              <CancelOutlinedIcon style={{ fontSize: 16 }} />
            )}
          </Box>
        </Tooltip>
        <span className={styles.metricScore}>{`${score.toFixed(1)}/${threshold.toFixed(1)}`}</span>
      </Box>
    );
  };

  const baseColumns: GridColDef<TestResultDetail>[] = [
    {
      field: 'prompt_name',
      headerName: 'Test',
      flex: 1,
      minWidth: 250,
      headerClassName: 'bold-header',
      renderCell: (params) => {
        const content = params.row.prompt_id && prompts[params.row.prompt_id]
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
      renderCell: (params) => {
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
  ];

  // Create metric columns grouped by behavior
  const metricColumns: GridColDef<TestResultDetail>[] = [];
  const columnGroupingModel: GridColumnGroupingModel = [];

  behaviors.forEach((behavior) => {
    if (behavior.metrics.length === 0) return;

    // Create columns for each metric in this behavior
    const behaviorMetricColumns = behavior.metrics.map((metric) => ({
      field: `${behavior.id}_${metric.id}`,
      headerName: metric.name.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' '),
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
          reason: metricResult.reason
        };
      },
    }));

    metricColumns.push(...behaviorMetricColumns);

    // Add column group for this behavior
    columnGroupingModel.push({
      groupId: behavior.id,
      headerName: behavior.name,
      description: behavior.description || undefined,
      children: behaviorMetricColumns.map(col => ({ field: col.field }))
    });
  });

  const columns = [...baseColumns, ...metricColumns];

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
          maxHeight: 'none'
        }
      }}
    >
      <DialogTitle className={styles.dialogTitle}>
        View Details
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent className={styles.dialogContent}>
        <Box className={styles.detailedGrid}>
          <DataGrid
            rows={testResults}
            columns={columns}
            columnGroupingModel={columnGroupingModel}
            loading={loading}
            pageSizeOptions={[10, 25, 50, 100]}
            paginationModel={paginationModel}
            onPaginationModelChange={handlePaginationModelChange}
            getRowId={(row) => row.id}
            density="compact"
            disableRowSelectionOnClick
            disableMultipleRowSelection
            disableColumnSelector
            disableColumnMenu
            disableColumnFilter
            disableColumnResize
            disableDensitySelector
            hideFooterSelectedRowCount
            paginationMode="server"
            rowCount={totalCount}
            onRowClick={handleRowClick}
            sx={{
              '& .MuiDataGrid-cell:focus': {
                outline: 'none',
              },
              '& .MuiDataGrid-cell:focus-within': {
                outline: 'none',
              },
              '& .MuiDataGrid-columnHeader:focus': {
                outline: 'none',
              },
              '& .MuiDataGrid-columnHeader:focus-within': {
                outline: 'none',
              },
            }}
          />
        </Box>
      </DialogContent>
    </Dialog>
  );
} 