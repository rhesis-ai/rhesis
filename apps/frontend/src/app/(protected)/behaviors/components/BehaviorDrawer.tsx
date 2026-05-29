'use client';

import React from 'react';
import {
  Typography,
  TextField,
  Button,
  Stack,
  Divider,
  Autocomplete,
  Chip,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import BaseDrawer from '@/components/common/BaseDrawer';
import { useFormChangeDetection } from '@/hooks/useFormChangeDetection';

interface BehaviorDrawerProps {
  open: boolean;
  onClose: () => void;
  name: string;
  description: string;
  initialTagNames?: string[];
  tagSuggestions?: string[];
  onSave: (name: string, description: string, tagNames: string[]) => void;
  onDuplicate?: () => void;
  onDelete?: () => void;
  isNew?: boolean;
  loading?: boolean;
  error?: string;
}

const sortedUnique = (values: string[]) =>
  Array.from(new Set(values.filter(v => v.trim().length > 0))).sort();

const BehaviorDrawer = ({
  open,
  onClose,
  name: initialName,
  description: initialDescription,
  initialTagNames = [],
  tagSuggestions = [],
  onSave,
  onDuplicate,
  onDelete,
  isNew = false,
  loading = false,
  error,
}: BehaviorDrawerProps) => {
  const [currentName, setCurrentName] = React.useState(initialName);
  const [currentDescription, setCurrentDescription] =
    React.useState(initialDescription);
  const [currentTagNames, setCurrentTagNames] =
    React.useState<string[]>(initialTagNames);
  const [validationError, setValidationError] = React.useState<string>('');

  const initialTagsSorted = React.useMemo(
    () => sortedUnique(initialTagNames),
    [initialTagNames]
  );
  const currentTagsSorted = React.useMemo(
    () => sortedUnique(currentTagNames),
    [currentTagNames]
  );

  const { hasChanges } = useFormChangeDetection({
    initialData: {
      name: initialName,
      description: initialDescription,
      tags: initialTagsSorted.join('\u0001'),
    },
    currentData: {
      name: currentName,
      description: currentDescription,
      tags: currentTagsSorted.join('\u0001'),
    },
  });

  React.useEffect(() => {
    if (open) {
      setCurrentName(initialName);
      setCurrentDescription(initialDescription);
      setCurrentTagNames(initialTagNames);
      setValidationError('');
    }
  }, [initialName, initialDescription, initialTagNames, open]);

  const handleSaveInternal = () => {
    setValidationError('');

    if (!isNew && !hasChanges) {
      return;
    }

    const trimmedName = currentName.trim();

    if (!trimmedName) {
      setValidationError('Behavior name is required');
      return;
    }

    if (trimmedName.length < 2) {
      setValidationError('Behavior name must be at least 2 characters');
      return;
    }

    onSave(
      trimmedName,
      currentDescription.trim(),
      sortedUnique(currentTagNames)
    );
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
      saveDisabled={!isNew && !hasChanges}
      loading={loading}
      error={error}
      width={600}
    >
      <Stack
        spacing={{ xs: 2, sm: 3 }}
        divider={!isNew && (onDelete || onDuplicate) ? <Divider /> : null}
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
            helperText={
              validationError || 'A clear, descriptive name for this behavior'
            }
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

          <Autocomplete
            multiple
            freeSolo
            options={tagSuggestions}
            value={currentTagNames}
            onChange={(_event, value) => {
              const normalized = value
                .map(v => v.trim())
                .filter(v => v.length > 0);
              setCurrentTagNames(Array.from(new Set(normalized)));
            }}
            disabled={loading}
            renderTags={(value: readonly string[], getTagProps) =>
              value.map((option, index) => {
                const { key, ...chipProps } = getTagProps({ index });
                return (
                  <Chip key={key} label={option} size="small" {...chipProps} />
                );
              })
            }
            renderInput={params => (
              <TextField
                {...params}
                label="Tags"
                placeholder={
                  currentTagNames.length === 0
                    ? 'Add tags to group behaviors (e.g. Marketing, US 1)'
                    : ''
                }
                helperText="Press Enter to add. Reuse tags from other behaviors to group them."
              />
            )}
          />
        </Stack>

        {/* Duplicate Section */}
        {!isNew && onDuplicate && (
          <Stack spacing={1.5}>
            <Typography variant="body2" color="text.secondary">
              Create a copy of this behavior
            </Typography>
            <Button
              variant="outlined"
              startIcon={<ContentCopyIcon />}
              onClick={onDuplicate}
              fullWidth
              disabled={loading}
            >
              Duplicate Behavior
            </Button>
          </Stack>
        )}

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
