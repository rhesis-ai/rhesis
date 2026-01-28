import React from 'react';
import { Typography, TextField, Button, Stack, Divider } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import BaseDrawer from '@/components/common/BaseDrawer';

interface BehaviorDrawerProps {
  open: boolean;
  onClose: () => void;
  name: string;
  description: string;
  onSave: (name: string, description: string) => void;
  onDelete?: () => void;
  isNew?: boolean;
  loading?: boolean;
  error?: string;
}

const BehaviorDrawer = ({
  open,
  onClose,
  name: initialName,
  description: initialDescription,
  onSave,
  onDelete,
  isNew = false,
  loading = false,
  error,
}: BehaviorDrawerProps) => {
  const [currentName, setCurrentName] = React.useState(initialName);
  const [currentDescription, setCurrentDescription] =
    React.useState(initialDescription);
  const [validationError, setValidationError] = React.useState<string>('');

  React.useEffect(() => {
    if (open) {
      setCurrentName(initialName);
      setCurrentDescription(initialDescription);
      setValidationError('');
    }
  }, [initialName, initialDescription, open]);

  const handleSaveInternal = () => {
    setValidationError('');

    const trimmedName = currentName.trim();

    if (!trimmedName) {
      setValidationError('Behavior name is required');
      return;
    }

    if (trimmedName.length < 2) {
      setValidationError('Behavior name must be at least 2 characters');
      return;
    }

    onSave(trimmedName, currentDescription.trim());
  };

  const drawerTitle = isNew ? 'Add New Behavior' : 'Edit Behavior';
  const saveButtonText = isNew ? 'Add Behavior' : 'Save Changes';

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={drawerTitle}
      onSave={handleSaveInternal}
      saveButtonText={saveButtonText}
      loading={loading}
      error={error}
      width={600}
    >
      <Stack
        spacing={{ xs: 2, sm: 3 }}
        divider={!isNew && onDelete ? <Divider /> : null}
        useFlexGap
      >
        {/* Main Section */}
        <Stack spacing={2}>
          <TextField
            label="Name"
            value={currentName}
            onChange={e => {
              setCurrentName(e.target.value);
              if (validationError) setValidationError('');
            }}
            fullWidth
            required
            variant="outlined"
            disabled={loading}
            error={!!validationError}
            helperText={validationError || "A clear, descriptive name for this behavior"}
          />

          <TextField
            label="Description"
            value={currentDescription}
            onChange={e => setCurrentDescription(e.target.value)}
            multiline
            rows={4}
            fullWidth
            variant="outlined"
            disabled={loading}
            helperText="Describe what this behavior measures and why it matters"
          />
        </Stack>

        {/* Delete Section */}
        {!isNew && onDelete && (
          <Stack spacing={1.5}>
            <Typography variant="body2" color="text.secondary">
              Delete this behavior (only available if no metrics are assigned)
            </Typography>
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={onDelete}
              fullWidth
              disabled={loading}
            >
              Delete Behavior
            </Button>
          </Stack>
        )}
      </Stack>
    </BaseDrawer>
  );
};

export default BehaviorDrawer;
