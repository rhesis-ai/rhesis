'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { GridColDef, GridRowSelectionModel, GridPaginationModel } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Box, Chip, Tooltip, FormControl, InputLabel, Select, MenuItem, SelectChangeEvent, Typography, Avatar } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useSession } from 'next-auth/react';
import AddIcon from '@mui/icons-material/Add';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PersonIcon from '@mui/icons-material/Person';
import TestSetDrawer from './TestSetDrawer';
import TestRunDrawer from './TestRunDrawer';

interface StatusInfo {
  label: string;
  borderColor: string;
  color: string;
}

const getStatusInfo = (testSet: TestSet & { status?: string | { name: string } }): StatusInfo => {
  // Only use actual status from API
  return {
    label: typeof testSet.status === "string" 
      ? testSet.status 
      : testSet.status && typeof testSet.status === "object" && 'name' in testSet.status 
        ? testSet.status.name 
        : "Unknown",
    borderColor: 'primary.light',
    color: 'primary.main'
  };
};

interface TestSetsGridProps {
  testSets: TestSet[];
  loading: boolean;
  sessionToken?: string;
  initialTotalCount?: number;
}

const ChipContainer = ({ items }: { items: string[] }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [visibleItems, setVisibleItems] = useState<string[]>([]);
  const [remainingCount, setRemainingCount] = useState(0);

  useEffect(() => {
    const calculateVisibleChips = () => {
      if (!containerRef.current || items.length === 0) return;

      const container = containerRef.current;
      const containerWidth = container.clientWidth;
      const tempDiv = document.createElement('div');
      tempDiv.style.visibility = 'hidden';
      tempDiv.style.position = 'absolute';
      document.body.appendChild(tempDiv);

      let totalWidth = 0;
      let visibleCount = 0;
      
      // Account for potential overflow chip width
      const overflowChip = document.createElement('div');
      overflowChip.innerHTML = '<span class="MuiChip-root" style="padding: 0 8px;">+99</span>';
      document.body.appendChild(overflowChip);
      const overflowChipWidth = (overflowChip.firstChild as HTMLElement)?.getBoundingClientRect().width || 0;
      overflowChip.remove();

      for (let i = 0; i < items.length; i++) {
        const chip = document.createElement('div');
        chip.innerHTML = `<span class="MuiChip-root" style="padding: 0 8px;">${items[i]}</span>`;
        tempDiv.appendChild(chip);
        const chipWidth = (chip.firstChild as HTMLElement)?.getBoundingClientRect().width || 0;
        
        if (totalWidth + chipWidth + (i < items.length - 1 ? overflowChipWidth : 0) <= containerWidth - 16) { // 16px for safety margin
          totalWidth += chipWidth + 8; // 8px for gap
          visibleCount++;
        } else {
          break;
        }
      }

      tempDiv.remove();
      setVisibleItems(items.slice(0, visibleCount));
      setRemainingCount(items.length - visibleCount);
    };

    calculateVisibleChips();
    window.addEventListener('resize', calculateVisibleChips);
    return () => window.removeEventListener('resize', calculateVisibleChips);
  }, [items]);

  if (items.length === 0) return '-';

  return (
    <Box ref={containerRef} sx={{ display: 'flex', gap: 0.5, alignItems: 'center', width: '100%', overflow: 'hidden' }}>
      {visibleItems.map((item: string) => (
        <Chip key={item} label={item} size="small" variant="outlined" />
      ))}
      {remainingCount > 0 && (
        <Tooltip title={items.slice(visibleItems.length).join(', ')} arrow>
          <Chip label={`+${remainingCount}`} size="small" variant="outlined" />
        </Tooltip>
      )}
    </Box>
  );
};

export default function TestSetsGrid({ 
  testSets: initialTestSets, 
  loading: initialLoading, 
  sessionToken,
  initialTotalCount 
}: TestSetsGridProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const [filteredTestSets, setFilteredTestSets] = useState<TestSet[]>(initialTestSets);
  const [loading, setLoading] = useState(initialLoading);
  const [testSets, setTestSets] = useState<TestSet[]>(initialTestSets);
  const [totalCount, setTotalCount] = useState<number>(initialTotalCount || initialTestSets.length);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [testRunDrawerOpen, setTestRunDrawerOpen] = useState(false);

  // Initial data fetch if needed
  useEffect(() => {
    const fetchInitialData = async () => {
      if (!sessionToken && !session?.session_token) return;
      
      try {
        setLoading(true);
        const token = sessionToken || session?.session_token;
        const clientFactory = new ApiClientFactory(token!);
        const testSetsClient = clientFactory.getTestSetsClient();
        
        const response = await testSetsClient.getTestSets({ 
          skip: 0,
          limit: paginationModel.pageSize,
          sort_by: 'created_at',
          sort_order: 'desc'
        });
        
        setTestSets(response.data);
        setTotalCount(response.pagination.totalCount);
      } catch (error) {
        console.error('Error fetching initial test sets:', error);
      } finally {
        setLoading(false);
      }
    };

    if (!initialTestSets.length) {
      fetchInitialData();
    }
  }, [sessionToken, session, initialTestSets, paginationModel.pageSize]);

  const fetchTestSets = useCallback(async () => {
    if (!sessionToken && !session?.session_token) return;
    
    try {
      setLoading(true);
      
      const token = sessionToken || session?.session_token;
      const clientFactory = new ApiClientFactory(token!);
      const testSetsClient = clientFactory.getTestSetsClient();
      
      const skip = paginationModel.page * paginationModel.pageSize;
      const limit = paginationModel.pageSize;
      
      const response = await testSetsClient.getTestSets({ 
                  skip, 
          limit,
          sort_by: 'created_at',
          sort_order: 'desc'
      });
      
      setTestSets(response.data);
      setTotalCount(response.pagination.totalCount);
    } catch (error) {
      console.error('Error fetching paginated test sets:', error);
    } finally {
      setLoading(false);
    }
  }, [sessionToken, session, paginationModel]);

  useEffect(() => {
    if (initialTestSets.length > 0) return;
    
    fetchTestSets();
  }, [initialTestSets.length, fetchTestSets, paginationModel.page, paginationModel.pageSize]);

  const handlePaginationModelChange = useCallback((newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  }, []);

  // Process test sets for display
  const processedTestSets = testSets.map(testSet => {
    const statusInfo = getStatusInfo(testSet as TestSet & { status?: string | { name: string } });

    return {
      id: testSet.id,
      name: testSet.name,
      behaviors: testSet.attributes?.metadata?.behaviors || [],
      categories: testSet.attributes?.metadata?.categories || [],
      totalTests: testSet.attributes?.metadata?.total_tests || 0,
      status: statusInfo.label,
      assignee: testSet.assignee
    };
  });

  const columns: GridColDef[] = [
    { 
      field: 'name',
      headerName: 'Name', 
      flex: 1.5,
      renderCell: (params) => <span style={{ fontWeight: 'medium' }}>{params.value}</span>
    },
    { 
      field: 'behaviors', 
      headerName: 'Behaviors', 
      flex: 1.0,
      renderCell: (params) => <ChipContainer items={params.value || []} />
    },
    { 
      field: 'categories', 
      headerName: 'Categories', 
      flex: 1.0,
      renderCell: (params) => <ChipContainer items={params.value || []} />
    },
    { field: 'totalTests', headerName: 'Tests', flex: 0.5 },
    { 
      field: 'status', 
      headerName: 'Status', 
      flex: 0.5,
      renderCell: (params) => <Chip label={params.value} size="small" variant="outlined" />
    },
    {
      field: 'assignee',
      headerName: 'Assignee',
      flex: 0.75,
      renderCell: (params) => {
        const assignee = params.value;
        if (!assignee) return '-';
        
        const displayName = assignee.name || 
          `${assignee.given_name || ''} ${assignee.family_name || ''}`.trim() || 
          assignee.email;

        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Avatar
              src={assignee.picture}
              sx={{ width: 24, height: 24 }}
            >
              <PersonIcon />
            </Avatar>
            <Typography variant="body2">{displayName}</Typography>
          </Box>
        );
      }
    }
  ];

  const handleRowClick = (params: any) => {
    router.push(`/test-sets/${params.id}`);
  };

  const handleNewTestSet = () => {
    setDrawerOpen(true);
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
  };

  const handleTestSetSaved = async () => {
    fetchTestSets();
  };

  const handleSelectionChange = (newSelection: GridRowSelectionModel) => {
    setSelectedRows(newSelection);
  };

  const handleRunTestSets = () => {
    setTestRunDrawerOpen(true);
  };

  const handleTestRunSuccess = () => {
    setTestRunDrawerOpen(false);
    // Optionally refresh the test sets list if needed
  };

  const getActionButtons = () => {
    const buttons = [
      {
        label: 'New Test Set',
        icon: <AddIcon />,
        variant: 'contained' as const,
        onClick: handleNewTestSet
      }
    ];

    if (selectedRows.length > 0) {
      buttons.push({
        label: 'Run Test Set',
        icon: <PlayArrowIcon />,
        variant: 'contained' as const,
        onClick: handleRunTestSets
      });
    }

    return buttons;
  };

  return (
    <>
      {selectedRows.length > 0 && (
        <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="subtitle1" color="primary">
            {selectedRows.length} test sets selected
          </Typography>
        </Box>
      )}

      <BaseDataGrid
        columns={columns}
        rows={processedTestSets}
        loading={loading}
        getRowId={(row) => row.id}
        showToolbar={false}
        onRowClick={handleRowClick}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        actionButtons={getActionButtons()}
        checkboxSelection
        disableRowSelectionOnClick
        onRowSelectionModelChange={handleSelectionChange}
        rowSelectionModel={selectedRows}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
      />

      {(sessionToken || session?.session_token) && (
        <>
          <TestSetDrawer
            open={drawerOpen}
            onClose={handleDrawerClose}
            sessionToken={sessionToken || session?.session_token!}
            onSuccess={handleTestSetSaved}
          />
          <TestRunDrawer
            open={testRunDrawerOpen}
            onClose={() => setTestRunDrawerOpen(false)}
            sessionToken={sessionToken || session?.session_token!}
            selectedTestSetIds={selectedRows as string[]}
            onSuccess={handleTestRunSuccess}
          />
        </>
      )}
    </>
  );
}