'use client';

import React, { useState, useCallback, DragEvent } from 'react';
import { GridColDef, GridPaginationModel, GridRenderCellParams } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Box, Chip, Tooltip, Typography, IconButton } from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

export interface AdaptiveTest {
  id: string;
  input: string;
  output: string;
  score: number | null;
  topic: string;
  label: string;
}

interface AdaptiveTestsGridProps {
  tests: AdaptiveTest[];
  loading: boolean;
  sessionToken?: string;
  enableDragDrop?: boolean;
  onEdit?: (test: AdaptiveTest) => void;
  onDelete?: (test: AdaptiveTest) => void;
}

const getScoreColor = (
  score: number | null
): 'success' | 'warning' | 'error' | 'default' => {
  if (score === null) return 'default';
  if (score >= 0.7) return 'error'; // High score = failure in adaptive testing
  if (score >= 0.3) return 'warning';
  return 'success';
};

const TruncatedCell = ({
  value,
  maxLength = 100,
}: {
  value: string;
  maxLength?: number;
}) => {
  const truncated = value.length > maxLength;
  const displayValue = truncated ? `${value.slice(0, maxLength)}...` : value;

  if (truncated) {
    return (
      <Tooltip title={value} arrow placement="top">
        <Typography
          variant="body2"
          sx={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {displayValue}
        </Typography>
      </Tooltip>
    );
  }

  return (
    <Typography
      variant="body2"
      sx={{
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}
    >
      {displayValue}
    </Typography>
  );
};

// Draggable cell component
const DraggableCell = ({
  params,
  children,
  enableDragDrop,
}: {
  params: GridRenderCellParams;
  children: React.ReactNode;
  enableDragDrop?: boolean;
}) => {
  const handleDragStart = (e: DragEvent<HTMLDivElement>) => {
    e.dataTransfer.setData('text/plain', params.row.id);
    e.dataTransfer.effectAllowed = 'move';
  };

  if (!enableDragDrop) {
    return <>{children}</>;
  }

  return (
    <Box
      draggable
      onDragStart={handleDragStart}
      sx={{
        display: 'flex',
        alignItems: 'center',
        width: '100%',
        cursor: 'grab',
        '&:active': { cursor: 'grabbing' },
      }}
    >
      <DragIndicatorIcon
        fontSize="small"
        sx={{ color: 'action.disabled', mr: 1, flexShrink: 0 }}
      />
      {children}
    </Box>
  );
};

export default function AdaptiveTestsGrid({
  tests,
  loading,
  enableDragDrop = false,
  onEdit,
  onDelete,
}: AdaptiveTestsGridProps) {
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const columns: GridColDef[] = [
    {
      field: 'input',
      headerName: 'Input',
      flex: 2,
      minWidth: 200,
      renderCell: params => (
        <DraggableCell params={params} enableDragDrop={enableDragDrop}>
          <TruncatedCell value={params.value || ''} />
        </DraggableCell>
      ),
    },
    {
      field: 'output',
      headerName: 'Output',
      flex: 2,
      minWidth: 200,
      renderCell: params => <TruncatedCell value={params.value || ''} />,
    },
    {
      field: 'score',
      headerName: 'Score',
      width: 120,
      align: 'center',
      headerAlign: 'center',
      renderCell: params => {
        const score = params.value;
        if (score === null || score === undefined) {
          return <Chip label="N/A" size="small" variant="outlined" />;
        }
        return (
          <Chip
            label={score.toFixed(2)}
            size="small"
            color={getScoreColor(score)}
            variant="filled"
          />
        );
      },
    },
    {
      field: 'label',
      headerName: 'Label',
      width: 120,
      renderCell: params => {
        const label = params.value;
        if (!label || label === 'topic_marker') return '-';
        return <Chip label={label} size="small" variant="outlined" />;
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      renderCell: params => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="Edit test">
            <IconButton
              size="small"
              onClick={e => {
                e.stopPropagation();
                onEdit?.(params.row as AdaptiveTest);
              }}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete test">
            <IconButton
              size="small"
              onClick={e => {
                e.stopPropagation();
                onDelete?.(params.row as AdaptiveTest);
              }}
              color="error"
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  return (
    <Box>
      {tests.length === 0 ? (
        <Box sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No adaptive tests found in this test set
          </Typography>
        </Box>
      ) : (
        <BaseDataGrid
          columns={columns}
          rows={tests}
          loading={loading}
          getRowId={row => row.id}
          showToolbar={false}
          paginationModel={paginationModel}
          onPaginationModelChange={handlePaginationModelChange}
          serverSidePagination={false}
          totalRows={tests.length}
          pageSizeOptions={[10, 25, 50, 100]}
          disablePaperWrapper={true}
          persistState
        />
      )}
    </Box>
  );
}
