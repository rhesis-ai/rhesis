'use client';

import * as React from 'react';
import { Box, Button, Slider, TextField, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import ViewField from '@/components/common/ViewField';
import {
  MultiTurnTestConfig,
  createEmptyMultiTurnConfig,
} from '@/utils/api-client/interfaces/multi-turn-test-config';

export type MultiTurnDraft = MultiTurnTestConfig;

interface MultiTurnConfigFieldsProps {
  draft: MultiTurnDraft;
  setDraft: (
    next: MultiTurnDraft | ((p: MultiTurnDraft) => MultiTurnDraft)
  ) => void;
  isEditing: boolean;
}

interface OptionalFieldConfig {
  key: 'instructions' | 'restrictions' | 'scenario';
  label: string;
  helperText: string;
  placeholder: string;
  maxLength: number;
}

const OPTIONAL_TEXT_FIELDS: OptionalFieldConfig[] = [
  {
    key: 'instructions',
    label: 'Instructions',
    helperText:
      'How to conduct the test — if not provided, the agent plans its own approach',
    placeholder: 'How to conduct the test',
    maxLength: 10000,
  },
  {
    key: 'restrictions',
    label: 'Restrictions',
    helperText:
      'What the target must not do — forbidden behaviors or boundaries',
    placeholder: 'What must not happen',
    maxLength: 10000,
  },
  {
    key: 'scenario',
    label: 'Scenario',
    helperText:
      'Context and persona for the test — narrative setup or user role',
    placeholder: 'Context and persona for the test',
    maxLength: 5000,
  },
];

const TURN_CONFIG_HELPER =
  'Set the minimum and maximum number of conversation turns';

interface EditableTextFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onRemove?: () => void;
  helperText: string;
  placeholder?: string;
  maxLength?: number;
  rows?: number;
  required?: boolean;
}

function EditableTextField({
  label,
  value,
  onChange,
  onRemove,
  helperText,
  placeholder,
  maxLength,
  rows = 4,
  required = false,
}: EditableTextFieldProps) {
  const charCount = value.length;
  const isOverLimit = maxLength ? charCount > maxLength : false;
  const isNearLimit = maxLength ? charCount > maxLength * 0.8 : false;
  const isEmptyRequired = required && value.trim().length === 0;

  const helperLine = (() => {
    if (isEmptyRequired) return `${label} cannot be empty`;
    if (maxLength) {
      return `${helperText} · ${charCount} / ${maxLength}`;
    }
    return helperText;
  })();

  return (
    <Box sx={{ width: '100%', position: 'relative' }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: '6px',
          px: '14px',
        }}
      >
        <Typography
          sx={{
            fontSize: 14,
            lineHeight: '22px',
            color: theme => theme.palette.greyscale.subtitle,
          }}
        >
          {label}
          {required ? ' *' : ''}
        </Typography>
        {onRemove && (
          <Button
            size="small"
            startIcon={<CloseIcon />}
            onClick={onRemove}
            sx={{ textTransform: 'none', fontWeight: 600 }}
          >
            Remove
          </Button>
        )}
      </Box>
      <TextField
        fullWidth
        multiline
        minRows={rows}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        inputProps={maxLength ? { maxLength } : undefined}
        error={isOverLimit || isEmptyRequired}
        helperText={helperLine}
        FormHelperTextProps={{
          sx: {
            fontSize: 12,
            lineHeight: '18px',
            mx: '14px',
            mt: '3px',
            color: theme =>
              isOverLimit || isEmptyRequired
                ? theme.palette.error.main
                : isNearLimit
                  ? theme.palette.warning.main
                  : theme.palette.greyscale.subtitle,
          },
        }}
      />
    </Box>
  );
}

export default function MultiTurnConfigFields({
  draft,
  setDraft,
  isEditing,
}: MultiTurnConfigFieldsProps) {
  const visibleOptional = React.useMemo(() => {
    if (isEditing) {
      // In edit mode, show every optional field that the user has either
      // populated or explicitly added during this edit session.
      return new Set(
        OPTIONAL_TEXT_FIELDS.filter(f => draft[f.key] !== undefined).map(
          f => f.key
        )
      );
    }
    // In view mode, only show optional fields that actually have content.
    return new Set(
      OPTIONAL_TEXT_FIELDS.filter(f => {
        const value = draft[f.key];
        return typeof value === 'string' && value.trim().length > 0;
      }).map(f => f.key)
    );
  }, [draft, isEditing]);

  const hiddenOptional = OPTIONAL_TEXT_FIELDS.filter(
    f => !visibleOptional.has(f.key)
  );

  const updateField = (
    field: keyof MultiTurnTestConfig,
    value: string | number | undefined
  ) => {
    setDraft(prev => ({
      ...prev,
      [field]: value,
    }));
  };

  const addOptional = (key: OptionalFieldConfig['key']) => {
    setDraft(prev => ({ ...prev, [key]: '' }));
  };

  const removeOptional = (key: OptionalFieldConfig['key']) => {
    setDraft(prev => ({ ...prev, [key]: undefined }));
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Goal — required, always visible */}
      {isEditing ? (
        <EditableTextField
          label="Goal"
          value={draft.goal ?? ''}
          onChange={v => updateField('goal', v)}
          helperText="What the target should do — the success criteria for this test"
          placeholder="What should be verified in this test"
          maxLength={5000}
          rows={4}
          required
        />
      ) : (
        <ViewField
          label="Goal"
          value={draft.goal}
          helperText="What the target should do — the success criteria for this test"
          multiline
        />
      )}

      {/* Optional text fields */}
      {OPTIONAL_TEXT_FIELDS.map(field => {
        if (!visibleOptional.has(field.key)) return null;
        const value = (draft[field.key] as string | undefined) ?? '';

        return isEditing ? (
          <EditableTextField
            key={field.key}
            label={field.label}
            value={value}
            onChange={v => updateField(field.key, v)}
            onRemove={() => removeOptional(field.key)}
            helperText={field.helperText}
            placeholder={field.placeholder}
            maxLength={field.maxLength}
            rows={4}
          />
        ) : (
          <ViewField
            key={field.key}
            label={field.label}
            value={value}
            helperText={field.helperText}
            multiline
          />
        );
      })}

      {/* Turn configuration — always visible, blends with the other fields */}
      <TurnConfigEditor
        draft={draft}
        setDraft={setDraft}
        disabled={!isEditing}
      />

      {/* Add optional field buttons — only in edit mode */}
      {isEditing && hiddenOptional.length > 0 && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
          {hiddenOptional.map(field => (
            <Button
              key={field.key}
              variant="outlined"
              size="small"
              startIcon={<AddIcon />}
              onClick={() => addOptional(field.key)}
              sx={{ textTransform: 'none' }}
            >
              {field.label}
            </Button>
          ))}
        </Box>
      )}
    </Box>
  );
}

interface TurnConfigEditorProps {
  draft: MultiTurnDraft;
  setDraft: (
    next: MultiTurnDraft | ((p: MultiTurnDraft) => MultiTurnDraft)
  ) => void;
  disabled?: boolean;
}

function TurnConfigEditor({
  draft,
  setDraft,
  disabled = false,
}: TurnConfigEditorProps) {
  const max = draft.max_turns ?? 10;
  const min = draft.min_turns ?? Math.ceil(max * 0.8);

  return (
    <Box sx={{ width: '100%' }}>
      {/* Label — matches ViewField */}
      <Typography
        sx={{
          fontSize: 14,
          lineHeight: '22px',
          color: theme => theme.palette.greyscale.subtitle,
          px: '14px',
          mb: '6px',
          whiteSpace: 'nowrap',
        }}
      >
        Turn Configuration
      </Typography>

      {/* Value box — matches ViewField */}
      <Box
        sx={{
          bgcolor: theme => theme.palette.greyscale.fieldSurface,
          borderRadius: '4px',
          pl: '16px',
          pr: '16px',
          py: '16px',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography
            sx={{
              fontSize: 14,
              lineHeight: '22px',
              minWidth: 64,
              color: theme => theme.palette.greyscale.body,
            }}
          >
            Min: {min}
          </Typography>
          <Slider
            value={[min, max]}
            onChange={(_, newValue) => {
              const [newMin, newMax] = newValue as number[];
              setDraft(prev => ({
                ...prev,
                min_turns: newMin,
                max_turns: newMax,
              }));
            }}
            min={1}
            max={50}
            step={1}
            marks={[
              { value: 1, label: '1' },
              { value: 10, label: '10' },
              { value: 25, label: '25' },
              { value: 50, label: '50' },
            ]}
            valueLabelDisplay="auto"
            disableSwap
            disabled={disabled}
          />
          <Typography
            sx={{
              fontSize: 14,
              lineHeight: '22px',
              minWidth: 64,
              textAlign: 'right',
              color: theme => theme.palette.greyscale.body,
            }}
          >
            Max: {max}
          </Typography>
        </Box>
      </Box>

      {/* Helper text below — matches ViewField */}
      <Typography
        sx={{
          fontSize: 12,
          lineHeight: '18px',
          color: theme => theme.palette.greyscale.subtitle,
          px: '14px',
          pt: '3px',
        }}
      >
        {TURN_CONFIG_HELPER}
      </Typography>
    </Box>
  );
}

export function createMultiTurnDraft(
  config: MultiTurnTestConfig | null | undefined
): MultiTurnDraft {
  return {
    ...createEmptyMultiTurnConfig(),
    ...(config ?? {}),
  };
}
