'use client';

import React, { useCallback, useMemo, useState } from 'react';
import { Box, Tooltip, Button } from '@mui/material';
import { formatDate } from '@/utils/date';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { GridColDef, GridPaginationModel, GridRenderCellParams, GridRowParams } from '@mui/x-data-grid';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DownloadIcon from '@mui/icons-material/Download';
import { useRouter } from 'next/navigation';
import DetailedTestRunGrid from './DetailedTestRunGrid';
import { useTestRunData } from '../hooks/useTestRunData';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';

interface TestRunTestsGridProps {
  testRunId: string;
  sessionToken: string;
}

export default function TestRunTestsGrid({ testRunId, sessionToken }: TestRunTestsGridProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const [detailedViewOpen, setDetailedViewOpen] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });

  const { testResults, prompts, behaviors, loading, totalCount, error } = useTestRunData({
    testRunId,
    sessionToken,
    paginationModel,
  });

  const handlePaginationModelChange = useCallback((newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  }, []);

  const handleRowClick = useCallback((params: GridRowParams<TestResultDetail>) => {
    if (params.row.test_id) {
      router.push(`/tests/${params.row.test_id}`);
    }
  }, [router]);

  const handleDownloadTestRun = useCallback(async () => {
    setIsDownloading(true);
    try {
      const testRunsClient = new ApiClientFactory(sessionToken).getTestRunsClient();
      const blob = await testRunsClient.downloadTestRun(testRunId);
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `test_run_${testRunId}_results.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      notifications.show('Test run results downloaded successfully', { severity: 'success' });
    } catch (error) {
      console.error('Error downloading test run:', error);
      notifications.show('Failed to download test run results', { severity: 'error' });
    } finally {
      setIsDownloading(false);
    }
  }, [testRunId, sessionToken, notifications]);

  const renderBehaviorCell = useCallback((params: GridRenderCellParams) => {
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
  }, []);

  const baseColumns: GridColDef<TestResultDetail>[] = useMemo(() => [
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
  ], [prompts]);

  const behaviorColumns: GridColDef<TestResultDetail>[] = useMemo(() => behaviors.map((behavior) => ({
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
  })), [behaviors, renderBehaviorCell]);

  const columns = useMemo(() => [...baseColumns, ...behaviorColumns], [baseColumns, behaviorColumns]);

  const customToolbarContent = useMemo(() => (
    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, p: 1 }}>
      <Button
        variant="outlined"
        startIcon={<VisibilityIcon />}
        onClick={() => setDetailedViewOpen(true)}
        size="small"
      >
        View Details
      </Button>
      <Button
        variant="outlined"
        startIcon={<DownloadIcon />}
        onClick={handleDownloadTestRun}
        disabled={isDownloading}
        size="small"
      >
        {isDownloading ? 'Downloading...' : 'Download'}
      </Button>
    </Box>
  ), [handleDownloadTestRun, isDownloading]);

  if (error) {
    return (
      <Box sx={{ p: 2, textAlign: 'center', color: 'error.main' }}>
        Error: {error}
      </Box>
    );
  }

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
        disablePaperWrapper={true}
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