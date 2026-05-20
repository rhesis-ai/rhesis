'use client';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  SvgIconProps,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import {
  AddIcon,
  CancelIcon,
  CategoryIcon,
  LockIcon,
  NotesIcon,
  NumbersIcon,
  SaveIcon,
  SmartToyIcon,
  TextFieldsIcon,
  ToggleOnIcon,
  TuneIcon,
} from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ParameterField,
  ParameterSchema,
  ParameterType,
  ParameterValue,
} from '@/utils/api-client/interfaces/parameters';
import { useNotifications } from '@/components/common/NotificationContext';

export interface FieldRowState extends ParameterField {
  _key: string;
}

export const TYPE_OPTIONS: ReadonlyArray<{
  value: ParameterType;
  label: string;
}> = [
  { value: 'text', label: 'Text (multiline)' },
  { value: 'string', label: 'String (single-line)' },
  { value: 'integer', label: 'Integer' },
  { value: 'number', label: 'Number' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'enum', label: 'Enum' },
  { value: 'model_ref', label: 'Model reference' },
  { value: 'secret_ref', label: 'Secret reference' },
];

interface TypeMeta {
  label: string;
  shortLabel: string;
  icon: React.ComponentType<SvgIconProps>;
  /** MUI palette path used to colour the type accent. */
  color:
    | 'primary'
    | 'secondary'
    | 'info'
    | 'success'
    | 'warning'
    | 'error'
    | 'default';
}

export const TYPE_META: Record<ParameterType, TypeMeta> = {
  text: {
    label: 'Text (multiline)',
    shortLabel: 'Text',
    icon: NotesIcon,
    color: 'info',
  },
  string: {
    label: 'String (single-line)',
    shortLabel: 'String',
    icon: TextFieldsIcon,
    color: 'primary',
  },
  integer: {
    label: 'Integer',
    shortLabel: 'Integer',
    icon: NumbersIcon,
    color: 'warning',
  },
  number: {
    label: 'Number',
    shortLabel: 'Number',
    icon: NumbersIcon,
    color: 'warning',
  },
  boolean: {
    label: 'Boolean',
    shortLabel: 'Boolean',
    icon: ToggleOnIcon,
    color: 'success',
  },
  enum: {
    label: 'Enum',
    shortLabel: 'Enum',
    icon: CategoryIcon,
    color: 'secondary',
  },
  model_ref: {
    label: 'Model reference',
    shortLabel: 'Model',
    icon: SmartToyIcon,
    color: 'secondary',
  },
  secret_ref: {
    label: 'Secret reference',
    shortLabel: 'Secret',
    icon: LockIcon,
    color: 'error',
  },
};

export function defaultForType(type: ParameterType): ParameterValue | null {
  switch (type) {
    case 'text':
      return { type: 'text', value: '' };
    case 'string':
      return { type: 'string', value: '' };
    case 'integer':
      return { type: 'integer', value: 0 };
    case 'number':
      return { type: 'number', value: 0 };
    case 'boolean':
      return { type: 'boolean', value: false };
    case 'enum':
      return null;
    case 'model_ref':
    case 'secret_ref':
      return null;
  }
}

export function blankField(displayOrder: number): ParameterField {
  return {
    name: '',
    type: 'string',
    required: false,
    description: '',
    default: null,
    options: null,
    display_order: displayOrder,
  };
}

export function stableKey(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

export function stripKeys(draft: FieldRowState[]): ParameterField[] {
  return draft.map(({ _key: _omit, ...rest }) => rest);
}

/**
 * Owns the parameter-schema draft + server reconciliation lifecycle so
 * the different visual variants only render UI.
 */
export function useParameterSchema(projectId: string, sessionToken: string) {
  const notifications = useNotifications();

  const [serverSchema, setServerSchema] = useState<ParameterSchema | null>(
    null
  );
  const [draft, setDraft] = useState<FieldRowState[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const fetchSchema = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const client = apiFactory.getParametersClient();
      const schema = await client.getSchema(projectId);
      setServerSchema(schema);
      setDraft(
        schema.fields.map(field => ({ ...field, _key: stableKey('f') }))
      );
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load parameter schema';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [apiFactory, projectId]);

  useEffect(() => {
    fetchSchema();
  }, [fetchSchema]);

  const isDirty = useMemo(() => {
    if (serverSchema === null) return false;
    return (
      JSON.stringify(serverSchema.fields) !== JSON.stringify(stripKeys(draft))
    );
  }, [serverSchema, draft]);

  const updateField = useCallback(
    (key: string, patch: Partial<FieldRowState>) => {
      setDraft(prev =>
        prev.map(row => (row._key === key ? { ...row, ...patch } : row))
      );
    },
    []
  );

  const changeType = useCallback((key: string, newType: ParameterType) => {
    setDraft(prev =>
      prev.map(row => {
        if (row._key !== key) return row;
        return {
          ...row,
          type: newType,
          default: defaultForType(newType),
          options: newType === 'enum' ? (row.options ?? []) : null,
        };
      })
    );
  }, []);

  const addField = useCallback(() => {
    const created: FieldRowState = {
      ...blankField(0),
      _key: stableKey('f'),
    };
    setDraft(prev => [...prev, { ...created, display_order: prev.length }]);
    return created._key;
  }, []);

  const removeField = useCallback((key: string) => {
    setDraft(prev =>
      prev
        .filter(row => row._key !== key)
        .map((row, i) => ({ ...row, display_order: i }))
    );
  }, []);

  const move = useCallback((key: string, direction: -1 | 1) => {
    setDraft(prev => {
      const idx = prev.findIndex(row => row._key === key);
      if (idx === -1) return prev;
      const target = idx + direction;
      if (target < 0 || target >= prev.length) return prev;
      const copy = [...prev];
      const [removed] = copy.splice(idx, 1);
      copy.splice(target, 0, removed);
      return copy.map((row, i) => ({ ...row, display_order: i }));
    });
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const payload: ParameterSchema = { fields: stripKeys(draft) };
      const client = apiFactory.getParametersClient();
      const saved = await client.putSchema(projectId, payload);
      setServerSchema(saved);
      setDraft(saved.fields.map(field => ({ ...field, _key: stableKey('f') })));
      notifications.show('Parameter schema saved', { severity: 'success' });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to save parameter schema';
      notifications.show(message, { severity: 'error' });
    } finally {
      setSaving(false);
    }
  }, [apiFactory, draft, notifications, projectId]);

  const handleRevert = useCallback(() => {
    if (!serverSchema) return;
    setDraft(
      serverSchema.fields.map(field => ({ ...field, _key: stableKey('f') }))
    );
  }, [serverSchema]);

  return {
    loading,
    error,
    saving,
    isDirty,
    draft,
    updateField,
    changeType,
    addField,
    removeField,
    move,
    handleSave,
    handleRevert,
  };
}

interface SaveBarProps {
  isDirty: boolean;
  saving: boolean;
  onSave: () => void;
  onRevert: () => void;
}

export function ParametersSaveBar({
  isDirty,
  saving,
  onSave,
  onRevert,
}: SaveBarProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'flex-end',
        gap: 1,
      }}
    >
      {isDirty && (
        <Button
          variant="outlined"
          color="error"
          startIcon={<CancelIcon />}
          onClick={onRevert}
          disabled={saving}
        >
          Discard
        </Button>
      )}
      <Button
        variant="contained"
        startIcon={<SaveIcon />}
        onClick={onSave}
        disabled={!isDirty || saving}
      >
        {saving ? 'Saving...' : 'Save Changes'}
      </Button>
    </Box>
  );
}

interface EmptyStateProps {
  onAdd: () => void;
}

export function ParametersEmptyState({ onAdd }: EmptyStateProps) {
  return (
    <Box
      sx={{
        py: 4,
        px: 2,
        border: '1px dashed',
        borderColor: 'divider',
        borderRadius: theme => theme.shape.borderRadius,
        textAlign: 'center',
        bgcolor: 'background.default',
      }}
    >
      <TuneIcon
        sx={{
          fontSize: theme => theme.typography.h3.fontSize,
          color: 'text.disabled',
          mb: 1,
          opacity: 0.5,
        }}
      />
      <Typography color="text.secondary" variant="body2" sx={{ mb: 2 }}>
        No parameter slots yet. Add a field to start defining the project&apos;s
        parameter schema.
      </Typography>
      <Button variant="outlined" startIcon={<AddIcon />} onClick={onAdd}>
        Add field
      </Button>
    </Box>
  );
}

interface FieldEditorProps {
  field: FieldRowState;
  onChange: (patch: Partial<FieldRowState>) => void;
  onTypeChange: (type: ParameterType) => void;
}

/**
 * Full vertical editor for a single field. Used by variants that show
 * one field at a time (master/detail) or that expand a field body
 * in-place (collapsible). For the legacy compact-row variant the
 * editing surface is composed inline.
 */
export function FieldEditor({
  field,
  onChange,
  onTypeChange,
}: FieldEditorProps) {
  return (
    <Stack spacing={2}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={2}
        alignItems={{ xs: 'stretch', md: 'center' }}
      >
        <TextField
          label="Name"
          value={field.name}
          onChange={e => onChange({ name: e.target.value })}
          size="small"
          fullWidth
          placeholder="snake_case identifier"
        />
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Type</InputLabel>
          <Select
            label="Type"
            value={field.type}
            onChange={e => onTypeChange(e.target.value as ParameterType)}
          >
            {TYPE_OPTIONS.map(opt => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={!!field.required}
              onChange={e => onChange({ required: e.target.checked })}
            />
          }
          label="Required"
        />
      </Stack>

      <TextField
        label="Description"
        value={field.description ?? ''}
        onChange={e => onChange({ description: e.target.value })}
        size="small"
        fullWidth
        multiline
        minRows={1}
      />

      {field.type === 'enum' && (
        <TextField
          label="Options (comma-separated)"
          value={(field.options ?? []).join(', ')}
          onChange={e =>
            onChange({
              options: e.target.value
                .split(',')
                .map(o => o.trim())
                .filter(Boolean),
            })
          }
          size="small"
          fullWidth
          helperText="The closed set of values this enum accepts"
        />
      )}

      <DefaultValueEditor field={field} onChange={onChange} />
    </Stack>
  );
}

interface DefaultValueEditorProps {
  field: FieldRowState;
  onChange: (patch: Partial<FieldRowState>) => void;
}

export function DefaultValueEditor({
  field,
  onChange,
}: DefaultValueEditorProps) {
  const setDefault = (value: ParameterValue | null) =>
    onChange({ default: value });

  switch (field.type) {
    case 'text': {
      const current =
        field.default && field.default.type === 'text'
          ? field.default.value
          : '';
      return (
        <TextField
          label="Default"
          value={current}
          onChange={e => setDefault({ type: 'text', value: e.target.value })}
          size="small"
          fullWidth
          multiline
          minRows={2}
        />
      );
    }
    case 'string': {
      const current =
        field.default && field.default.type === 'string'
          ? field.default.value
          : '';
      return (
        <TextField
          label="Default"
          value={current}
          onChange={e => setDefault({ type: 'string', value: e.target.value })}
          size="small"
          fullWidth
        />
      );
    }
    case 'integer': {
      const current =
        field.default && field.default.type === 'integer'
          ? field.default.value
          : '';
      return (
        <TextField
          label="Default"
          type="number"
          value={current}
          onChange={e => {
            const v = e.target.value;
            setDefault(
              v === '' ? null : { type: 'integer', value: parseInt(v, 10) }
            );
          }}
          size="small"
          inputProps={{ step: 1 }}
        />
      );
    }
    case 'number': {
      const current =
        field.default && field.default.type === 'number'
          ? field.default.value
          : '';
      return (
        <TextField
          label="Default"
          type="number"
          value={current}
          onChange={e => {
            const v = e.target.value;
            setDefault(
              v === '' ? null : { type: 'number', value: parseFloat(v) }
            );
          }}
          size="small"
          inputProps={{ step: 'any' }}
        />
      );
    }
    case 'boolean': {
      const current =
        field.default && field.default.type === 'boolean'
          ? field.default.value
          : false;
      return (
        <FormControlLabel
          control={
            <Switch
              checked={current}
              onChange={e =>
                setDefault({ type: 'boolean', value: e.target.checked })
              }
            />
          }
          label={
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="body2" color="text.secondary">
                Default
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {current ? 'True' : 'False'}
              </Typography>
            </Stack>
          }
        />
      );
    }
    case 'enum': {
      const options = field.options ?? [];
      const current =
        field.default && field.default.type === 'enum'
          ? field.default.value
          : '';
      return (
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Default</InputLabel>
          <Select
            label="Default"
            value={options.includes(current) ? current : ''}
            onChange={e => {
              const v = e.target.value as string;
              setDefault(v ? { type: 'enum', value: v } : null);
            }}
          >
            <MenuItem value="">
              <em>(none)</em>
            </MenuItem>
            {options.map(opt => (
              <MenuItem key={opt} value={opt}>
                {opt}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      );
    }
    case 'model_ref': {
      const current =
        field.default && field.default.type === 'model_ref'
          ? String(field.default.value)
          : '';
      return (
        <TextField
          label="Default model id"
          value={current}
          onChange={e => {
            const v = e.target.value.trim();
            setDefault(v ? { type: 'model_ref', value: v } : null);
          }}
          size="small"
          fullWidth
          helperText="UUID of a Model row"
        />
      );
    }
    case 'secret_ref': {
      const current =
        field.default && field.default.type === 'secret_ref'
          ? String(field.default.value)
          : '';
      return (
        <TextField
          label="Default secret id"
          value={current}
          onChange={e => {
            const v = e.target.value.trim();
            setDefault(v ? { type: 'secret_ref', value: v } : null);
          }}
          size="small"
          fullWidth
          helperText="UUID of a secret record"
        />
      );
    }
  }
}
