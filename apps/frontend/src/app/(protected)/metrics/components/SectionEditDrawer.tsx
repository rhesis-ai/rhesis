import React from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Stack
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import BaseDrawer from '@/components/common/BaseDrawer';

interface SectionEditDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description: string;
  onSave: (title: string, description: string) => void;
  onDelete: () => void;
  isNew?: boolean;
}

export default function SectionEditDrawer({
  open,
  onClose,
  title: initialTitle,
  description: initialDescription,
  onSave,
  onDelete,
  isNew = false
}: SectionEditDrawerProps) {
  const [title, setTitle] = React.useState(initialTitle);
  const [description, setDescription] = React.useState(initialDescription);

  React.useEffect(() => {
    setTitle(initialTitle);
    setDescription(initialDescription);
  }, [initialTitle, initialDescription]);

  const handleSave = () => {
    onSave(title, description);
    onClose();
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={isNew ? 'Add New Dimension' : 'Edit Dimension'}
      onSave={handleSave}
      saveButtonText={isNew ? 'Add Dimension' : 'Save Changes'}
    >
      <Stack spacing={3}>
        <TextField
          label="Dimension Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          fullWidth
        />
        <TextField
          label="Dimension Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          multiline
          rows={4}
          fullWidth
        />
        
        {!isNew && (
          <Box sx={{ mt: 2 }}>
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={onDelete}
              fullWidth
            >
              Delete Dimension
            </Button>
          </Box>
        )}
      </Stack>
    </BaseDrawer>
  );
} 