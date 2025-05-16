'use client';

import { useEffect, useState } from 'react';
import { Box, Tooltip } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { formatDate } from '@/utils/date';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { TestResult, TestResultDetail, MetricResult } from '@/utils/api-client/interfaces/test-results';
import { Prompt } from '@/utils/api-client/interfaces/prompt';
import { GridColDef, GridPaginationModel, GridRenderCellParams, GridRowParams } from '@mui/x-data-grid';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useRouter } from 'next/navigation';

interface TestRunTestsGridProps {
  testRunId: string;
  sessionToken: string;
}

export default function TestRunTestsGrid({ testRunId, sessionToken }: TestRunTestsGridProps) {
  const router = useRouter();
  const [testResults, setTestResults] = useState<TestResultDetail[]>([]);
  const [prompts, setPrompts] = useState<Record<string, Prompt>>({});
  const [loading, setLoading] = useState(true);
  const [metricNames, setMetricNames] = useState<string[]>([]);
  const [metricDescriptions, setMetricDescriptions] = useState<Record<string, string>>({});
  const [totalCount, setTotalCount] = useState<number>(0);
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

        // Extract all unique metric names and descriptions from the results
        const allMetricNames = new Set<string>();
        const descriptions: Record<string, string> = {};
        
        results.forEach((result) => {
          if (result.test_metrics?.metrics) {
            Object.entries(result.test_metrics.metrics).forEach(([name, metric]: [string, MetricResult]) => {
              allMetricNames.add(name);
              if (metric.description) {
                descriptions[name] = metric.description;
              }
            });
          }
        });
        
        setMetricNames(Array.from(allMetricNames));
        setMetricDescriptions(descriptions);
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

  const renderMetricCell = (params: GridRenderCellParams) => {
    const value = params.value;
    if (value === 'N/A') return value;
    
    const { status, score, threshold, reason } = value as { status: string; score: number; threshold: number; reason: string };
    const color = status === 'Passed' ? 'success.main' : 'error.main';
    
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
          title={reason ?? 'No reason provided'} 
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
        <span>{`(${score.toFixed(1)} / ${threshold.toFixed(1)})`}</span>
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

  const metricColumns: GridColDef<TestResultDetail>[] = metricNames.map((metricName) => ({
    field: metricName,
    headerName: '',
    width: 180,
    renderHeader: () => (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <span>
          {metricName.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}
        </span>
        <Tooltip 
          title={metricDescriptions[metricName] ?? 'No description available'} 
          enterDelay={1000}
          leaveDelay={0}
          enterNextDelay={1000}
        >
          <InfoOutlinedIcon sx={{ fontSize: 16, color: 'action.active', opacity: 0.8 }} />
        </Tooltip>
      </Box>
    ),
    renderCell: renderMetricCell,
    valueGetter: (_, row) => {
      const metric = row.test_metrics?.metrics?.[metricName];
      if (!metric) return 'N/A';
      return {
        status: metric.is_successful ? 'Passed' : 'Failed',
        score: metric.score,
        threshold: metric.threshold,
        reason: metric.reason
      };
    },
  }));

  const columns = [...baseColumns, ...metricColumns];

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
        showToolbar={false}
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
    </Box>
  );
} 