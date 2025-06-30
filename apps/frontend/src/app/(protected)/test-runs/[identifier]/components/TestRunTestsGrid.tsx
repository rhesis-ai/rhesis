'use client';

import { useEffect, useState } from 'react';
import { Box, Tooltip, Button } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { formatDate } from '@/utils/date';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { TestResult, TestResultDetail, MetricResult } from '@/utils/api-client/interfaces/test-results';
import { Prompt } from '@/utils/api-client/interfaces/prompt';
import { Behavior } from '@/utils/api-client/interfaces/behavior';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import { GridColDef, GridPaginationModel, GridRenderCellParams, GridRowParams } from '@mui/x-data-grid';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useRouter } from 'next/navigation';
import { UUID } from 'crypto';
import DetailedTestRunGrid from './DetailedTestRunGrid';

interface TestRunTestsGridProps {
  testRunId: string;
  sessionToken: string;
}

interface BehaviorWithMetrics extends Behavior {
  metrics: MetricDetail[];
}

export default function TestRunTestsGrid({ testRunId, sessionToken }: TestRunTestsGridProps) {
  const router = useRouter();
  const [testResults, setTestResults] = useState<TestResultDetail[]>([]);
  const [prompts, setPrompts] = useState<Record<string, Prompt>>({});
  const [loading, setLoading] = useState(true);
  const [behaviors, setBehaviors] = useState<BehaviorWithMetrics[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [detailedViewOpen, setDetailedViewOpen] = useState(false);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });

  useEffect(() => {
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
          sort_by: 'created_at',
          sort_order: 'desc'
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
  }, [testRunId, sessionToken, paginationModel]);

  const handlePaginationModelChange = (newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  };

  const handleRowClick = (params: GridRowParams<TestResultDetail>) => {
    if (params.row.test_id) {
      router.push(`/tests/${params.row.test_id}`);
    }
  };

  const renderBehaviorCell = (params: GridRenderCellParams) => {
    const value = params.value;
    if (value === 'N/A') return value;
    
    const { status, passedMetrics, totalMetrics, failedMetrics } = value as { 
      status: string; 
      passedMetrics: number; 
      totalMetrics: number; 
      failedMetrics: string[];
    };
    const color = status === 'Passed' ? 'success.main' : 'error.main';
    
    const tooltipContent = status === 'Passed' 
      ? `All ${totalMetrics} metrics passed`
      : `${passedMetrics}/${totalMetrics} metrics passed. Failed: ${failedMetrics.join(', ')}`;
    
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          width: '100%',
          height: '100%',
          gap: 1,
          color
        }}
      >
        <Tooltip 
          title={tooltipContent} 
          enterDelay={1000}
          leaveDelay={0}
          enterNextDelay={1000}
        >
          <Box component="span" sx={{ display: 'flex' }}>
            {status === 'Passed' ? (
              <CheckCircleOutlineIcon sx={{ color }} />
            ) : (
              <CancelOutlinedIcon sx={{ color }} />
            )}
          </Box>
        </Tooltip>
        <span>{`(${passedMetrics}/${totalMetrics})`}</span>
      </Box>
    );
  };

  const baseColumns: GridColDef<TestResultDetail>[] = [
    {
      field: 'prompt_name',
      headerName: 'Test',
      flex: 1,
      minWidth: 200,
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
            <Box sx={{ width: '100%', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {content.substring(0, 50) + '...'}
            </Box>
          </Tooltip>
        );
      },
    },
    {
      field: 'response',
      headerName: 'Response',
      flex: 1,
      minWidth: 200,
      renderCell: (params) => {
        const content = params.row.test_output?.output ?? 'N/A';
        return (
          <Tooltip 
            title={content} 
            enterDelay={1500}
            leaveDelay={0}
            enterNextDelay={1500}
          >
            <Box sx={{ width: '100%', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {content === 'N/A' ? content : content.substring(0, 50) + '...'}
            </Box>
          </Tooltip>
        );
      },
    },
  ];

  const behaviorColumns: GridColDef<TestResultDetail>[] = behaviors.map((behavior) => ({
    field: behavior.id,
    headerName: '',
    width: 180,
    renderHeader: () => (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <span>
          {behavior.name}
        </span>
        <Tooltip 
          title={behavior.description ?? 'No description available'} 
          enterDelay={1000}
          leaveDelay={0}
          enterNextDelay={1000}
        >
          <InfoOutlinedIcon sx={{ fontSize: 16, color: 'action.active', opacity: 0.8 }} />
        </Tooltip>
      </Box>
    ),
    renderCell: renderBehaviorCell,
    valueGetter: (_, row) => {
      const testMetrics = row.test_metrics?.metrics;
      if (!testMetrics || behavior.metrics.length === 0) return 'N/A';
      
      // Check each metric associated with this behavior
      let passedMetrics = 0;
      const failedMetrics: string[] = [];
      
      behavior.metrics.forEach((metric) => {
        const metricResult = testMetrics[metric.name];
        if (metricResult) {
          if (metricResult.is_successful) {
            passedMetrics++;
          } else {
            failedMetrics.push(metric.name);
          }
        }
      });
      
      const totalMetrics = behavior.metrics.length;
      const allPassed = passedMetrics === totalMetrics && failedMetrics.length === 0;
      
      return {
        status: allPassed ? 'Passed' : 'Failed',
        passedMetrics,
        totalMetrics,
        failedMetrics
      };
    },
  }));

  const columns = [...baseColumns, ...behaviorColumns];

  const customToolbarContent = (
    <Box sx={{ display: 'flex', justifyContent: 'flex-end', p: 1 }}>
      <Button
        variant="outlined"
        startIcon={<VisibilityIcon />}
        onClick={() => setDetailedViewOpen(true)}
        size="small"
      >
        View Details
      </Button>
    </Box>
  );

  return (
    <Box>
      <BaseDataGrid
        title="Test Run Results"
        rows={testResults}
        columns={columns}
        loading={loading}
        pageSizeOptions={[10, 25, 50]}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        getRowId={(row) => row.id}
        onRowClick={handleRowClick}
        showToolbar={true}
        customToolbarContent={customToolbarContent}
        density="compact"
        disableRowSelectionOnClick
        disableMultipleRowSelection
        serverSidePagination={true}
        totalRows={totalCount}
        sx={{
          '& .MuiDataGrid-row': {
            cursor: 'pointer',
            '&:hover': {
              backgroundColor: 'action.hover',
            },
          },
        }}
      />
      
      <DetailedTestRunGrid
        testRunId={testRunId}
        sessionToken={sessionToken}
        open={detailedViewOpen}
        onClose={() => setDetailedViewOpen(false)}
      />
    </Box>
  );
} 