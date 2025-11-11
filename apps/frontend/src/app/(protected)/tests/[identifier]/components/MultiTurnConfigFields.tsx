'use client';

import * as React from 'react';
import {
  Box,
  Grid,
  TextField,
  Typography,
  Button,
  useTheme,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import CancelIcon from '@mui/icons-material/Cancel';
import CheckIcon from '@mui/icons-material/Check';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import {
  MultiTurnTestConfig,
  createEmptyMultiTurnConfig,
} from '@/utils/api-client/interfaces/multi-turn-test-config';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { UUID } from 'crypto';

interface MultiTurnConfigFieldsProps {
  sessionToken: string;
  testId: UUID;
  initialConfig?: MultiTurnTestConfig | null;
  onUpdate?: () => void;
}

interface EditableFieldProps {
  label: string;
  value: string | number;
  onSave: (value: string | number) => Promise<void>;
  multiline?: boolean;
  rows?: number;
  type?: 'text' | 'number';
  placeholder?: string;
  helperText?: string;
  onRemove?: () => void;
  maxLength?: number;
}

function EditableField({
  label,
  value,
  onSave,
  multiline = true,
  rows = 3,
  type = 'text',
  placeholder = '',
  helperText = '',
  onRemove,
  maxLength,
}: EditableFieldProps) {
  const theme = useTheme();
  const [isEditing, setIsEditing] = React.useState(false);
  const [editedValue, setEditedValue] = React.useState(value);
  const [isUpdating, setIsUpdating] = React.useState(false);

  // Update local state when prop value changes
  React.useEffect(() => {
    setEditedValue(value);
  }, [value]);

  const displayRows = rows;

  // Calculate character count for text fields
  const charCount = type === 'text' ? String(editedValue || '').length : 0;
  const isNearLimit = Boolean(maxLength && charCount > maxLength * 0.8);
  const isOverLimit = Boolean(maxLength && charCount > maxLength);

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedValue(value);
  };

  const handleConfirmEdit = async () => {
    setIsUpdating(true);
    try {
      await onSave(editedValue);
      setIsEditing(false);
    } catch (error) {
      // Error notification is shown by parent
      // Revert to original value and exit edit mode
      setEditedValue(value);
      setIsEditing(false);
    } finally {
      setIsUpdating(false);
    }
  };

  const displayValue =
    type === 'number' ? value : !value || value === '' ? ' ' : String(value);

  return (
    <Grid item xs={12}>
      <Box sx={{ mb: 1 }}>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          {label}
        </Typography>
        {helperText && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', fontStyle: 'italic' }}
          >
            {helperText}
          </Typography>
        )}
      </Box>
      <Box sx={{ position: 'relative' }}>
        {isEditing ? (
          <>
            <TextField
              fullWidth
              multiline={multiline}
              rows={multiline ? displayRows : undefined}
              type={type}
              value={editedValue}
              onChange={e =>
                setEditedValue(
                  type === 'number'
                    ? parseInt(e.target.value) || 10
                    : e.target.value
                )
              }
              placeholder={placeholder}
              inputProps={
                type === 'number'
                  ? { min: 1, max: 50 }
                  : maxLength
                    ? { maxLength }
                    : undefined
              }
              error={isOverLimit}
              sx={{ mb: 1 }}
              autoFocus
            />
            {type === 'text' && maxLength && (
              <Typography
                variant="caption"
                color={
                  isOverLimit
                    ? 'error'
                    : isNearLimit
                      ? 'warning.main'
                      : 'text.secondary'
                }
                sx={{ display: 'block', mb: 1 }}
              >
                {charCount} / {maxLength} characters
                {isOverLimit && ' (exceeds maximum)'}
              </Typography>
            )}
          </>
        ) : (
          <Typography
            component="pre"
            variant="body2"
            sx={theme => ({
              whiteSpace: 'pre-wrap',
              fontFamily: 'monospace',
              bgcolor: 'action.hover',
              borderRadius: theme.shape.borderRadius * 0.25,
              p: 1,
              minHeight: multiline
                ? `calc(${displayRows} * 1.4375em + ${theme.spacing(2)})`
                : theme.spacing(6.75),
              pr: multiline
                ? onRemove
                  ? theme.spacing(21)
                  : theme.spacing(10)
                : onRemove
                  ? theme.spacing(24)
                  : theme.spacing(14),
              wordBreak: 'break-word',
              display: multiline ? 'block' : 'flex',
              alignItems: multiline ? undefined : 'center',
            })}
          >
            {displayValue}
          </Typography>
        )}

        {!isEditing ? (
          <Box
            sx={theme => ({
              position: 'absolute',
              top: theme.spacing(1),
              right: theme.spacing(1),
              zIndex: 1,
              display: 'flex',
              gap: 1,
            })}
          >
            {onRemove && (
              <Button
                startIcon={<CloseIcon />}
                onClick={onRemove}
                sx={theme => ({
                  backgroundColor:
                    theme.palette.mode === 'dark'
                      ? theme.palette.action.hover
                      : theme.palette.background.paper,
                  '&:hover': {
                    backgroundColor:
                      theme.palette.mode === 'dark'
                        ? theme.palette.action.selected
                        : theme.palette.action.hover,
                  },
                })}
              >
                Remove
              </Button>
            )}
            <Button
              startIcon={<EditIcon />}
              onClick={handleEdit}
              sx={theme => ({
                backgroundColor:
                  theme.palette.mode === 'dark'
                    ? theme.palette.action.hover
                    : theme.palette.background.paper,
                '&:hover': {
                  backgroundColor:
                    theme.palette.mode === 'dark'
                      ? theme.palette.action.selected
                      : theme.palette.action.hover,
                },
              })}
            >
              Edit
            </Button>
          </Box>
        ) : (
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
            <Button
              variant="outlined"
              color="error"
              startIcon={<CancelIcon />}
              onClick={handleCancelEdit}
              disabled={isUpdating}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              color="primary"
              startIcon={<CheckIcon />}
              onClick={handleConfirmEdit}
              disabled={isUpdating}
            >
              Confirm
            </Button>
          </Box>
        )}
      </Box>
    </Grid>
  );
}

export default function MultiTurnConfigFields({
  sessionToken,
  testId,
  initialConfig,
  onUpdate,
}: MultiTurnConfigFieldsProps) {
  const [config, setConfig] = React.useState<MultiTurnTestConfig>(
    initialConfig || createEmptyMultiTurnConfig()
  );
  const [showInstructions, setShowInstructions] = React.useState(
    !!initialConfig?.instructions
  );
  const [showRestrictions, setShowRestrictions] = React.useState(
    !!initialConfig?.restrictions
  );
  const [showScenario, setShowScenario] = React.useState(
    !!initialConfig?.scenario
  );
  const [showMaxTurns, setShowMaxTurns] = React.useState(
    !!initialConfig?.max_turns && initialConfig.max_turns !== 10
  );
  const notifications = useNotifications();

  // Update config when initialConfig changes
  React.useEffect(() => {
    if (initialConfig) {
      setConfig(initialConfig);
      setShowInstructions(!!initialConfig.instructions);
      setShowRestrictions(!!initialConfig.restrictions);
      setShowScenario(!!initialConfig.scenario);
      setShowMaxTurns(
        !!initialConfig.max_turns && initialConfig.max_turns !== 10
      );
    }
  }, [initialConfig]);

  const updateField = async (
    field: keyof MultiTurnTestConfig,
    value: string | number
  ) => {
    // Validate that goal is not empty before saving
    if (field === 'goal' && (!value || String(value).trim().length === 0)) {
      notifications.show('Goal cannot be empty', {
        severity: 'error',
        autoHideDuration: 3000,
      });
      throw new Error('Goal cannot be empty');
    }

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testsClient = apiFactory.getTestsClient();

      const updatedConfig = {
        ...config,
        [field]: value || undefined,
      };

      await testsClient.updateTest(testId, {
        test_configuration: updatedConfig as any,
      });

      setConfig(updatedConfig);

      notifications.show(`Successfully updated ${field.replace('_', ' ')}`, {
        severity: 'success',
        autoHideDuration: 3000,
      });

      if (onUpdate) {
        onUpdate();
      }
    } catch (error: any) {
      notifications.show(
        `Failed to update ${field.replace('_', ' ')}: ${error.message || 'Unknown error'}`,
        {
          severity: 'error',
          autoHideDuration: 6000,
        }
      );
      throw error;
    }
  };

  const removeField = async (
    field: keyof MultiTurnTestConfig,
    setShowFunction: (show: boolean) => void
  ) => {
    try {
      // Determine default value based on field
      let defaultValue: string | number;
      if (field === 'max_turns') {
        defaultValue = 10;
      } else {
        defaultValue = ''; // For text fields (instructions, restrictions, scenario)
      }

      // Update the field to its default value
      await updateField(field, defaultValue);

      // Hide the field after successful update
      setShowFunction(false);
    } catch (error) {
      // Error is already handled in updateField
    }
  };

  const optionalFields = [
    {
      key: 'instructions',
      show: showInstructions,
      setShow: setShowInstructions,
      label: 'Instructions',
    },
    {
      key: 'restrictions',
      show: showRestrictions,
      setShow: setShowRestrictions,
      label: 'Restrictions',
    },
    {
      key: 'scenario',
      show: showScenario,
      setShow: setShowScenario,
      label: 'Scenario',
    },
    {
      key: 'max_turns',
      show: showMaxTurns,
      setShow: setShowMaxTurns,
      label: 'Max. Turns',
    },
  ];

  const hiddenFields = optionalFields.filter(field => !field.show);

  return (
    <Grid container spacing={2}>
      <EditableField
        label="Goal"
        value={config.goal || ''}
        onSave={value => updateField('goal', value)}
        rows={3}
        placeholder="What should be verified in this test"
        helperText="What the target should do - the success criteria for this test"
        maxLength={5000}
      />

      {showInstructions && (
        <EditableField
          label="Instructions (Optional)"
          value={config.instructions || ''}
          onSave={value => updateField('instructions', value)}
          rows={3}
          placeholder="How to conduct the test"
          helperText="How to conduct the test - if not provided, the agent plans its own approach"
          onRemove={() => removeField('instructions', setShowInstructions)}
          maxLength={10000}
        />
      )}

      {showRestrictions && (
        <EditableField
          label="Restrictions (Optional)"
          value={config.restrictions || ''}
          onSave={value => updateField('restrictions', value)}
          rows={3}
          placeholder="What must not happen"
          helperText="What the target must not do - forbidden behaviors or boundaries"
          onRemove={() => removeField('restrictions', setShowRestrictions)}
          maxLength={10000}
        />
      )}

      {showScenario && (
        <EditableField
          label="Scenario (Optional)"
          value={config.scenario || ''}
          onSave={value => updateField('scenario', value)}
          rows={3}
          placeholder="Context and persona for the test"
          helperText="Context and persona for the test - narrative setup or user role"
          onRemove={() => removeField('scenario', setShowScenario)}
          maxLength={5000}
        />
      )}

      {showMaxTurns && (
        <EditableField
          label="Max. Turns"
          value={config.max_turns || 10}
          onSave={value => updateField('max_turns', value)}
          multiline={false}
          type="number"
          placeholder="10"
          helperText="Maximum number of conversation turns allowed (default: 10, max: 50)"
          onRemove={() => removeField('max_turns', setShowMaxTurns)}
        />
      )}

      {hiddenFields.length > 0 && (
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {hiddenFields.map(field => (
              <Button
                key={field.key}
                variant="outlined"
                size="small"
                startIcon={<AddIcon />}
                onClick={() => field.setShow(true)}
                sx={{ textTransform: 'none' }}
              >
                {field.label}
              </Button>
            ))}
          </Box>
        </Grid>
      )}
    </Grid>
  );
}
