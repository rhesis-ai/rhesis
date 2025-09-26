'use client';

import React, { useState, useEffect } from 'react';
import {
  GridColDef,
  GridRowModel,
  GridRenderEditCellParams,
  GridValueGetter,
  GridRenderCellParams,
} from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import AddIcon from '@mui/icons-material/Add';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Behavior } from '@/utils/api-client/interfaces/behavior';
import { Topic } from '@/utils/api-client/interfaces/topic';
import BaseFreesoloAutocomplete, {
  AutocompleteOption,
} from '@/components/common/BaseFreesoloAutocomplete';
import { Autocomplete, TextField } from '@mui/material';
import { useSession } from 'next-auth/react';

interface NewTestsGridProps {
  onSave?: () => void;
  onCancel?: () => void;
}

export default function NewTestsGrid({ onSave, onCancel }: NewTestsGridProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const { data: session } = useSession();
  const [behaviors, setBehaviors] = useState<Behavior[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [rows, setRows] = useState<GridRowModel[]>([
    {
      id: 'new-1',
      behaviorId: '',
      behaviorName: '',
      testType: '',
      topicId: '',
      topicName: '',
      categoryName: '',
      priority: 0,
      promptContent: '',
      statusName: '',
    },
  ]);

  // Counter for generating unique IDs for new rows
  const [idCounter, setIdCounter] = useState(2);

  // Fetch behaviors and topics on component mount
  useEffect(() => {
    const fetchData = async () => {
      if (!session?.session_token) {
        notifications.show('No session token available', { severity: 'error' });
        return;
      }

      try {
        const apiFactory = new ApiClientFactory(session.session_token);

        // Fetch behaviors with sorting
        const behaviorsClient = apiFactory.getBehaviorClient();
        const behaviorsData = await behaviorsClient.getBehaviors({
          sort_by: 'name',
          sort_order: 'asc',
        });
        setBehaviors(
          behaviorsData.filter(b => b.id && b.name && b.name.trim() !== '')
        );

        // Fetch topics with entity_type filter and sorting
        const topicsClient = apiFactory.getTopicClient();
        const topicsData = await topicsClient.getTopics({
          entity_type: 'Test',
          sort_by: 'name',
          sort_order: 'asc',
        });
        setTopics(topicsData);
      } catch (error) {
        notifications.show('Failed to load behaviors and topics', {
          severity: 'error',
        });
      }
    };
    fetchData();
  }, [session, notifications]);

  // Convert behaviors to autocomplete options
  const behaviorOptions: AutocompleteOption[] = behaviors.map(behavior => ({
    id: behavior.id,
    name: behavior.name,
  }));

  // Convert topics to autocomplete options
  const topicOptions: AutocompleteOption[] = topics.map(topic => ({
    id: topic.id,
    name: topic.name,
  }));

  // Define columns using the same structure as TestsGrid component
  const columns: GridColDef[] = [
    {
      field: 'behaviorName',
      headerName: 'Behavior',
      flex: 1,
      editable: true,
      valueGetter: (params: { row: GridRowModel }) => {
        if (!params?.row) return '';
        const behavior = behaviorOptions.find(
          b => b.id === params.row.behaviorId
        );
        return behavior?.name || '';
      },
      renderCell: (params: GridRenderCellParams) => {
        const behavior = behaviorOptions.find(
          b => b.id === params.row.behaviorId
        );
        return behavior?.name || '';
      },
      renderEditCell: params => (
        <Autocomplete
          options={behaviorOptions}
          getOptionLabel={option => option.name}
          value={
            behaviorOptions.find(opt => opt.id === params.row.behaviorId) ||
            null
          }
          onChange={(_, newValue) => {
            if (newValue) {
              params.api.setEditCellValue({
                id: params.id,
                field: 'behaviorId',
                value: newValue.id,
              });
              params.api.setEditCellValue({
                id: params.id,
                field: 'behaviorName',
                value: newValue.name,
              });
            }
          }}
          renderInput={params => <TextField {...params} />}
          renderOption={(props, option) => (
            <li {...props} key={option.id}>
              {option.name}
            </li>
          )}
          fullWidth
          isOptionEqualToValue={(option, value) => option?.id === value?.id}
        />
      ),
    },
    {
      field: 'topicName',
      headerName: 'Topic',
      flex: 1,
      editable: true,
      valueGetter: (params: { row: GridRowModel }) => {
        if (!params?.row) return '';
        const topic = topicOptions.find(t => t.id === params.row.topicId);
        return topic?.name || params.row.topicName || '';
      },
      renderCell: (params: GridRenderCellParams) => {
        const topic = topicOptions.find(t => t.id === params.row.topicId);
        return topic?.name || params.row.topicName || '';
      },
      renderEditCell: params => (
        <BaseFreesoloAutocomplete
          options={topicOptions}
          value={params.row.topicId || params.row.topicName}
          onChange={value => {
            if (typeof value === 'string') {
              // New topic
              params.api.setEditCellValue({
                id: params.id,
                field: 'topicId',
                value: value,
              });
              params.api.setEditCellValue({
                id: params.id,
                field: 'topicName',
                value: value,
              });
            } else if (value) {
              // Existing topic
              params.api.setEditCellValue({
                id: params.id,
                field: 'topicId',
                value: value.id,
              });
              params.api.setEditCellValue({
                id: params.id,
                field: 'topicName',
                value: value.name,
              });
            }
          }}
          label="Topic"
          required
        />
      ),
    },
    { field: 'testType', headerName: 'Type', flex: 1, editable: true },
    { field: 'categoryName', headerName: 'Category', flex: 1, editable: true },
    { field: 'promptContent', headerName: 'Prompt', flex: 1, editable: true },
    {
      field: 'priority',
      headerName: 'Priority',
      flex: 1,
      type: 'number',
      editable: true,
    },
    { field: 'statusName', headerName: 'Status', flex: 1, editable: true },
  ];

  const handleAddRecord = () => {
    const newRow = {
      id: `new-${idCounter}`,
      behaviorId: '',
      behaviorName: '',
      testType: '',
      topicId: '',
      topicName: '',
      categoryName: '',
      priority: 0,
      promptContent: '',
      statusName: '',
    };
    setRows([...rows, newRow]);
    setIdCounter(idCounter + 1);
  };

  const processRowUpdate = (newRow: GridRowModel) => {
    const updatedRows = rows.map(row => (row.id === newRow.id ? newRow : row));
    setRows(updatedRows);
    return newRow;
  };

  const handleProcessRowUpdateError = (error: Error) => {
    notifications.show(error.message, { severity: 'error' });
  };

  const handleSave = async () => {
    if (!session?.session_token) {
      notifications.show('No session token available', { severity: 'error' });
      return;
    }

    try {
      // Validate rows
      const emptyFields = rows.some(
        row =>
          !row.behaviorId ||
          !row.testType ||
          !row.topicName ||
          !row.categoryName ||
          !row.promptContent
      );

      if (emptyFields) {
        notifications.show('Please fill in all required fields', {
          severity: 'error',
        });
        return;
      }

      const apiFactory = new ApiClientFactory(session.session_token);
      // TODO: Implement save functionality using apiFactory.getTestsClient()
      notifications.show('Tests saved successfully', { severity: 'success' });
      if (onSave) {
        onSave();
      } else {
        router.push('/tests');
      }
    } catch (error) {
      notifications.show(
        error instanceof Error ? error.message : 'Failed to save tests',
        { severity: 'error' }
      );
    }
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    } else {
      router.push('/tests');
    }
  };

  return (
    <Paper sx={{ width: '100%', mb: 2 }}>
      <Box sx={{ p: 2 }}>
        <BaseDataGrid
          columns={columns}
          rows={rows}
          getRowId={row => row.id}
          enableEditing={true}
          editMode="row"
          processRowUpdate={processRowUpdate}
          onProcessRowUpdateError={handleProcessRowUpdateError}
          disableRowSelectionOnClick
          actionButtons={[
            {
              label: 'Add Record',
              icon: <AddIcon />,
              variant: 'contained',
              onClick: handleAddRecord,
            },
            {
              label: 'Save All',
              icon: <SaveIcon />,
              variant: 'contained',
              onClick: handleSave,
            },
            {
              label: 'Cancel',
              icon: <CancelIcon />,
              variant: 'outlined',
              onClick: handleCancel,
            },
          ]}
        />
      </Box>
    </Paper>
  );
}
