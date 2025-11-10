import React from 'react';
import {
  Typography,
  TextField,
  Button,
  Stack,
  Divider,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import BaseDrawer from '@/components/common/BaseDrawer';
import { UUID } from 'crypto';

interface SectionEditDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description: string;
  onSave: (title: string, description: string, organization_id: UUID) => void;
  onDelete?: () => void;
  isNew?: boolean;
  loading?: boolean;
  error?: string;
  entityName?: string;
  organization_id: UUID;
}

const SectionEditDrawer = ({
  open,
  onClose,
  title: initialTitle,
  description: initialDescription,
  onSave,
  onDelete,
  isNew = false,
  loading = false,
  error,
  entityName = 'Behavior',
  organization_id,
}: SectionEditDrawerProps) => {
  const [currentTitle, setCurrentTitle] = React.useState(initialTitle);
  const [currentDescription, setCurrentDescription] =
    React.useState(initialDescription);

  React.useEffect(() => {
    setCurrentTitle(initialTitle);
    setCurrentDescription(initialDescription);
  }, [initialTitle, initialDescription, open]);

  const handleSaveInternal = () => {
    onSave(currentTitle, currentDescription, organization_id);
  };

  const drawerTitle = isNew ? `Add New ${entityName}` : `Edit ${entityName}`;
  const saveButtonText = isNew ? `Add ${entityName}` : 'Save Changes';

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
            value={currentTitle}
            onChange={e => setCurrentTitle(e.target.value)}
            fullWidth
            required
            variant="outlined"
            disabled={loading}
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
          />
        </Stack>

        {/* Danger Zone Section */}
        {!isNew && onDelete && (
          <Stack spacing={2}>
            <Typography variant="subtitle2" color="text.secondary">
              Danger Zone
            </Typography>
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={onDelete}
              fullWidth
              disabled={loading}
            >
              Delete {entityName}
            </Button>
          </Stack>
        )}
      </Stack>
    </BaseDrawer>
  );
};

export default SectionEditDrawer;
