import * as React from 'react';
import { IconButton, TextField } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import BaseTable from '@/components/common/BaseTable';
import AddIcon from '@mui/icons-material/Add';

interface BaseTableProps {
  columns: { id: string; label: string; render: (row: any) => any }[];
  data: any[];
  addButton?: {
    label: string;
    onClick: () => void;
  };
}

interface EditableTableProps {
  data: any[];
  columns: { id: string; label: string }[];
  onUpdate: (newData: any[]) => void;
}

export default function EditableTable({ data, columns, onUpdate }: EditableTableProps) {
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [editingData, setEditingData] = React.useState<any>({});

  const handleEdit = (row: any) => {
    setEditingId(row.id);
    setEditingData(row);
  };

  const handleSave = () => {
    const newData = data.map((row) =>
      row.id === editingId ? editingData : row
    );
    onUpdate(newData);
    setEditingId(null);
  };

  const handleCancel = () => {
    setEditingId(null);
  };

  const handleDelete = (id: string) => {
    const newData = data.filter((row) => row.id !== id);
    onUpdate(newData);
  };

  const handleAdd = () => {
    const newRow = {
      id: `new-${Date.now()}`,
      ...columns.reduce((acc, col) => ({ ...acc, [col.id]: '' }), {}),
    };
    onUpdate([...data, newRow]);
    handleEdit(newRow);
  };

  const tableColumns = [
    ...columns.map(column => ({
      id: column.id,
      label: column.label,
      render: (row: any) => 
        editingId === row.id ? (
          <TextField
            fullWidth
            value={editingData[column.id]}
            onChange={(e) =>
              setEditingData({
                ...editingData,
                [column.id]: e.target.value,
              })
            }
            size="small"
            multiline={column.id === 'responsibilities'}
          />
        ) : (
          row[column.id]
        )
    })),
    {
      id: 'actions',
      label: 'Actions',
      render: (row: any) => 
        editingId === row.id ? (
          <>
            <IconButton onClick={handleSave} size="small">
              <SaveIcon />
            </IconButton>
            <IconButton onClick={handleCancel} size="small">
              <CancelIcon />
            </IconButton>
          </>
        ) : (
          <>
            <IconButton onClick={() => handleEdit(row)} size="small">
              <EditIcon />
            </IconButton>
            <IconButton onClick={() => handleDelete(row.id)} size="small">
              <DeleteIcon />
            </IconButton>
          </>
        )
    }
  ];

  return (
    <BaseTable
      columns={tableColumns}
      data={data}
      actionButtons={[{
        label: 'Add New Row',
        onClick: handleAdd,
        icon: <AddIcon />
      }]}
    />
  );
} 